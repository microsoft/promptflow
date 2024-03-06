# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
import os
import typing
import urllib.parse
import uuid

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.environment_variables import OTEL_EXPORTER_OTLP_ENDPOINT
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from promptflow._constants import (
    OTEL_RESOURCE_SERVICE_NAME,
    SpanAttributeFieldName,
    SpanResourceAttributesFieldName,
    TraceEnvironmentVariableName,
)
from promptflow._core.openai_injector import inject_openai_api
from promptflow._core.operation_context import OperationContext
from promptflow._sdk._configuration import Configuration
from promptflow._sdk._constants import PF_TRACE_CONTEXT, AzureMLWorkspaceTriad
from promptflow._sdk._service.utils.utils import is_pfs_service_healthy
from promptflow._sdk._utils import extract_workspace_triad_from_trace_provider
from promptflow._utils.logger_utils import get_cli_sdk_logger

_logger = get_cli_sdk_logger()


def start_trace(*, session: typing.Optional[str] = None, **kwargs):
    """Start a tracing session.

    This will capture OpenAI and prompt flow related calls and persist traces;
    it will also provide a UI url for user to visualize traces details.

    Note that this function is still under preview, and may change at any time.
    """
    # trace is currently a preview feature, users should explicitly enable to use it
    if Configuration.get_instance().is_internal_features_enabled() is False:
        warning_message = (
            "`start_trace` is currently a preview feature, "
            'please enable it with `pf config set enable_internal_features="true"`'
        )
        _logger.warning(warning_message)
        return

    from promptflow._sdk._constants import ContextAttributeKey
    from promptflow._sdk._service.utils.utils import get_port_from_config

    pfs_port = get_port_from_config(create_if_not_exists=True)
    _start_pfs(pfs_port)
    _logger.debug("Promptflow service is serving on port %s", pfs_port)

    # set strict limitation for session id currently
    if session is not None:
        _validate_session_id(session)
    session_id = _provision_session_id(specified_session_id=session)
    _logger.debug("current session id is %s", session_id)

    operation_context = OperationContext.get_instance()

    # honor and set attributes if user has specified
    attributes: dict = kwargs.get("attributes", None)
    if attributes is not None:
        _logger.debug("User specified attributes: %s", attributes)
        for attr_key, attr_value in attributes.items():
            operation_context._add_otel_attributes(attr_key, attr_value)

    # prompt flow related, retrieve `experiment` and `referenced.line_run_id`
    env_trace_context = os.environ.get(PF_TRACE_CONTEXT, None)
    _logger.debug("Read trace context from environment: %s", env_trace_context)
    env_attributes = json.loads(env_trace_context).get("attributes") if env_trace_context else {}
    experiment = env_attributes.get(ContextAttributeKey.EXPERIMENT, None)
    ref_line_run_id = env_attributes.get(ContextAttributeKey.REFERENCED_LINE_RUN_ID, None)
    # Remove reference line run id if it's None to avoid stale value set by previous node
    if ref_line_run_id is None:
        operation_context._remove_otel_attributes(SpanAttributeFieldName.REFERENCED_LINE_RUN_ID)
    else:
        operation_context._add_otel_attributes(SpanAttributeFieldName.REFERENCED_LINE_RUN_ID, ref_line_run_id)

    # trace provider from pf config, for local to cloud scenario
    workspace_triad = _get_workspace_triad_from_config()

    # init the global tracer with endpoint
    _init_otel_trace_exporter(
        otlp_port=pfs_port,
        session_id=session_id,
        experiment=experiment,
        workspace_triad=workspace_triad,
    )

    # print url(s) for user to view the trace
    print_url_kwargs = {
        "session_configured": session is not None,
        "experiment": experiment,
        "run": kwargs.get("run", None),
        "session_id": session_id,
    }
    _print_trace_url_for_local(pfs_port=pfs_port, **print_url_kwargs)
    _print_trace_url_for_local_to_cloud(workspace_triad=workspace_triad, **print_url_kwargs)


def _start_pfs(pfs_port) -> None:
    from promptflow._sdk._service.entry import entry
    from promptflow._sdk._service.utils.utils import is_port_in_use

    command_args = ["start", "--port", str(pfs_port)]
    if is_port_in_use(pfs_port):
        is_healthy = is_pfs_service_healthy(pfs_port)
        if not is_healthy:
            command_args += ["--force"]
        else:
            return
    entry(command_args)


def _is_tracer_provider_configured() -> bool:
    # if tracer provider is configured, `tracer_provider` should be an instance of `TracerProvider`;
    # otherwise, it should be an instance of `ProxyTracerProvider`
    tracer_provider = trace.get_tracer_provider()
    return isinstance(tracer_provider, TracerProvider)


def _provision_session_id(specified_session_id: typing.Optional[str]) -> str:
    # check if session id is configured in tracer provider
    configured_session_id = None
    if _is_tracer_provider_configured():
        tracer_provider: TracerProvider = trace.get_tracer_provider()
        configured_session_id = tracer_provider._resource.attributes[SpanResourceAttributesFieldName.SESSION_ID]

    if specified_session_id is None and configured_session_id is None:
        # user does not specify and not configured, provision a new one
        session_id = str(uuid.uuid4())
    elif specified_session_id is None and configured_session_id is not None:
        # user does not specify, but already configured, use the configured one
        session_id = configured_session_id
    elif specified_session_id is not None and configured_session_id is None:
        # user specified, but not configured, use the specified one
        session_id = specified_session_id
    else:
        # user specified while configured, log warnings and honor the configured one
        session_id = configured_session_id
        warning_message = (
            f"Session is already configured with id: {session_id!r}, "
            "we will honor it within current process; "
            "if you expect another session, please specify it in another process."
        )
        _logger.warning(warning_message)
    return session_id


def _create_resource(
    session_id: str,
    experiment: typing.Optional[str] = None,
    workspace_triad: typing.Optional[AzureMLWorkspaceTriad] = None,
) -> Resource:
    resource_attributes = {
        SpanResourceAttributesFieldName.SERVICE_NAME: OTEL_RESOURCE_SERVICE_NAME,
        SpanResourceAttributesFieldName.SESSION_ID: session_id,
    }
    if experiment is not None:
        resource_attributes[SpanResourceAttributesFieldName.EXPERIMENT_NAME] = experiment
    if workspace_triad is not None:
        resource_attributes[SpanResourceAttributesFieldName.SUBSCRIPTION_ID] = workspace_triad.subscription_id
        resource_attributes[SpanResourceAttributesFieldName.RESOURCE_GROUP_NAME] = workspace_triad.resource_group_name
        resource_attributes[SpanResourceAttributesFieldName.WORKSPACE_NAME] = workspace_triad.workspace_name
    return Resource(attributes=resource_attributes)


def setup_exporter_from_environ() -> None:
    # openai instrumentation
    # in eager mode, the code cannot reach executor logic to apply injection
    # explicitly inject here, so that it can work in new process/thread
    inject_openai_api()
    # if session id does not exist in environment variables, it should be in runtime environment
    # where we have not supported tracing yet, so we don't need to setup any exporter here
    # directly return
    if TraceEnvironmentVariableName.SESSION_ID not in os.environ:
        return
    if _is_tracer_provider_configured():
        _logger.debug("tracer provider is already configured, skip setting up again.")
        return

    # get resource values from environment variables
    session_id = os.getenv(TraceEnvironmentVariableName.SESSION_ID)
    experiment = os.getenv(TraceEnvironmentVariableName.EXPERIMENT, None)
    # local to cloud: trace provider
    workspace_triad = None
    subscription_id = os.getenv(TraceEnvironmentVariableName.SUBSCRIPTION_ID, None)
    resource_group_name = os.getenv(TraceEnvironmentVariableName.RESOURCE_GROUP_NAME, None)
    workspace_name = os.getenv(TraceEnvironmentVariableName.WORKSPACE_NAME, None)
    if all([subscription_id, resource_group_name, workspace_name]):
        workspace_triad = AzureMLWorkspaceTriad(
            subscription_id=subscription_id,
            resource_group_name=resource_group_name,
            workspace_name=workspace_name,
        )
    # create resource
    resource = _create_resource(
        session_id=session_id,
        experiment=experiment,
        workspace_triad=workspace_triad,
    )
    tracer_provider = TracerProvider(resource=resource)
    # get OTLP endpoint from environment variable
    endpoint = os.getenv(OTEL_EXPORTER_OTLP_ENDPOINT)
    # Set timeout as 30 seconds since creating cosmosDB client is time consuming
    otlp_span_exporter = OTLPSpanExporter(endpoint=endpoint, timeout=30)
    tracer_provider.add_span_processor(BatchSpanProcessor(otlp_span_exporter))
    trace.set_tracer_provider(tracer_provider)


def _init_otel_trace_exporter(
    otlp_port: str,
    session_id: str,
    experiment: typing.Optional[str] = None,
    workspace_triad: typing.Optional[AzureMLWorkspaceTriad] = None,
) -> None:
    endpoint = f"http://localhost:{otlp_port}/v1/traces"
    os.environ[OTEL_EXPORTER_OTLP_ENDPOINT] = endpoint
    os.environ[TraceEnvironmentVariableName.SESSION_ID] = session_id
    if experiment is not None:
        os.environ[TraceEnvironmentVariableName.EXPERIMENT] = experiment
    if workspace_triad is not None:
        os.environ[TraceEnvironmentVariableName.SUBSCRIPTION_ID] = workspace_triad.subscription_id
        os.environ[TraceEnvironmentVariableName.RESOURCE_GROUP_NAME] = workspace_triad.resource_group_name
        os.environ[TraceEnvironmentVariableName.WORKSPACE_NAME] = workspace_triad.workspace_name
    setup_exporter_from_environ()


# priority: run > experiment > session
# for run(s) in experiment, we should print url with run(s) as it is more specific;
# and url with experiment should be printed at the beginning of experiment start.
# session id is the concept we expect to expose to users least, so it should have the lowest priority.
def _print_trace_url_for_local(
    pfs_port: str,
    session_configured: bool,
    experiment: typing.Optional[str] = None,
    run: typing.Optional[str] = None,
    session_id: typing.Optional[str] = None,
) -> None:
    url = f"http://localhost:{pfs_port}/v1.0/ui/traces"
    if run is not None:
        url += f"?run={run}"
    elif experiment is not None:
        url += f"?experiment={experiment}"
    elif session_configured and session_id is not None:
        url += f"?session={session_id}"
    print(f"You can view the trace from local PFS: {url}")


def _print_trace_url_for_local_to_cloud(
    workspace_triad: typing.Optional[AzureMLWorkspaceTriad],
    session_configured: bool,
    experiment: typing.Optional[str] = None,
    run: typing.Optional[str] = None,
    session_id: typing.Optional[str] = None,
) -> None:
    # if user has configured trace.provider, we can extract workspace triad from it
    # this indicates local to cloud feature is enabled, then print the url in portal
    if workspace_triad is None:
        return
    # &searchText={"sessionId":"8baa9e34-3d23-497a-8ec8-39b84cdb7a40","batchRunId":"test_main_variant_0_20240229_111938_229535"}
    url = (
        "https://int.ml.azure.com/prompts/trace/list"
        f"?wsid=/subscriptions/{workspace_triad.subscription_id}"
        f"/resourceGroups/{workspace_triad.resource_group_name}"
        "/providers/Microsoft.MachineLearningServices"
        f"/workspaces/{workspace_triad.workspace_name}"
    )
    query = None
    if run is not None:
        query = '{"batchRunId":"' + run + '"}'
    elif experiment is not None:
        # not consider experiment for now
        pass
    elif session_configured and session_id is not None:
        query = '{"sessionId":"' + session_id + '"}'
    # urllib.parse.quote to encode the query parameter
    if query is not None:
        url += f"&searchText={urllib.parse.quote(query)}"
    print(f"You can view the trace in cloud from Azure portal: {url}")


def _get_workspace_triad_from_config() -> typing.Optional[AzureMLWorkspaceTriad]:
    trace_provider = Configuration.get_instance().get_trace_provider()
    if trace_provider is None:
        return None
    return extract_workspace_triad_from_trace_provider(trace_provider)


def _validate_session_id(value: str) -> None:
    # session id should only contain `[A-Z, a-z, 0-9, _, -]`` for now
    if not value.replace("-", "").replace("_", "").isalnum():
        raise ValueError("session id should only contain `[A-Z, a-z, 0-9, _, -]` for now.")
