# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import os
import typing
import urllib.parse

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
from promptflow._sdk._configuration import Configuration
from promptflow._sdk._constants import (
    PF_TRACE_CONTEXT,
    PF_TRACE_CONTEXT_ATTR,
    AzureMLWorkspaceTriad,
    ContextAttributeKey,
)
from promptflow._sdk._service.entry import entry
from promptflow._sdk._service.utils.utils import get_port_from_config, is_pfs_service_healthy, is_port_in_use
from promptflow._sdk._utils import extract_workspace_triad_from_trace_provider
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow.tracing._integrations._openai_injector import inject_openai_api
from promptflow.tracing._operation_context import OperationContext
from promptflow.tracing._start_trace import _force_set_tracer_provider, _is_tracer_provider_set

logger = get_cli_sdk_logger()


def get_ws_tracing_base_url(ws_triad: AzureMLWorkspaceTriad) -> str:
    return (
        "https://int.ml.azure.com/prompts/trace/list"
        f"?wsid=/subscriptions/{ws_triad.subscription_id}"
        f"/resourceGroups/{ws_triad.resource_group_name}"
        "/providers/Microsoft.MachineLearningServices"
        f"/workspaces/{ws_triad.workspace_name}"
    )


def _inject_attrs_to_op_ctx(attrs: typing.Dict[str, str]) -> None:
    if len(attrs) == 0:
        return
    logger.debug("Inject attributes %s to context", attrs)
    op_ctx = OperationContext.get_instance()
    for attr_key, attr_value in attrs.items():
        op_ctx._add_otel_attributes(attr_key, attr_value)


def _invoke_pf_svc() -> str:
    port = get_port_from_config(create_if_not_exists=True)
    port = str(port)
    cmd_args = ["start", "--port", port]
    if is_port_in_use(int(port)):
        if not is_pfs_service_healthy(port):
            cmd_args.append("--force")
        else:
            return port
    entry(cmd_args)
    logger.debug("Prompt flow service is serving on port %s", port)
    return port


def _get_ws_triad_from_pf_config() -> typing.Optional[AzureMLWorkspaceTriad]:
    ws_arm_id = Configuration.get_instance().get_trace_provider()
    return extract_workspace_triad_from_trace_provider(ws_arm_id) if ws_arm_id is not None else None


# priority: run > experiment > session id
# for run(s) in experiment, we should print url with run(s) as it is more specific;
# and url with experiment should be printed at the beginning of experiment start.
# session id is the concept we expect to expose to users least, so it should have the lowest priority.
def _print_tracing_url_from_local(
    pfs_port: str,
    session_id: typing.Optional[str],
    exp: typing.Optional[str] = None,
    run: typing.Optional[str] = None,
) -> None:
    url = f"http://localhost:{pfs_port}/v1.0/ui/traces/"
    if run is not None:
        url += f"?#run={run}"
    elif exp is not None:
        url += f"?#experiment={exp}"
    elif session_id is not None:
        url += f"?#session={session_id}"
    print(f"You can view the traces from local: {url}")


def _print_tracing_url_from_azure_portal(
    ws_triad: typing.Optional[AzureMLWorkspaceTriad],
    session_id: typing.Optional[str],
    exp: typing.Optional[str] = None,
    run: typing.Optional[str] = None,
) -> None:
    if ws_triad is None:
        return
    url = get_ws_tracing_base_url(ws_triad)
    query = None
    if run is not None:
        query = '{"batchRunId":"' + run + '"}'
    elif exp is not None:
        # not consider experiment for now
        pass
    elif session_id is not None:
        query = '{"sessionId":"' + session_id + '"}'
    # urllib.parse.quote to encode the query parameter
    if query is not None:
        url += f"&searchText={urllib.parse.quote(query)}"
    print(f"You can view the traces in cloud from Azure portal: {url}")


def _inject_res_attrs_to_environ(
    pfs_port: str,
    session_id: typing.Optional[str],
    exp: typing.Optional[str] = None,
    ws_triad: typing.Optional[AzureMLWorkspaceTriad] = None,
) -> None:
    if session_id is not None:
        os.environ[TraceEnvironmentVariableName.SESSION_ID] = session_id
    if exp is not None:
        os.environ[TraceEnvironmentVariableName.EXPERIMENT] = exp
    if ws_triad is not None:
        os.environ[TraceEnvironmentVariableName.SUBSCRIPTION_ID] = ws_triad.subscription_id
        os.environ[TraceEnvironmentVariableName.RESOURCE_GROUP_NAME] = ws_triad.resource_group_name
        os.environ[TraceEnvironmentVariableName.WORKSPACE_NAME] = ws_triad.workspace_name
    # we will not overwrite the value if it is already set
    if OTEL_EXPORTER_OTLP_ENDPOINT not in os.environ:
        os.environ[OTEL_EXPORTER_OTLP_ENDPOINT] = f"http://localhost:{pfs_port}/v1/traces"


def _create_or_merge_res(
    session_id: typing.Optional[str],
    exp: typing.Optional[str] = None,
    ws_triad: typing.Optional[AzureMLWorkspaceTriad] = None,
) -> Resource:
    res_attrs = dict()
    if session_id is not None:
        res_attrs[SpanResourceAttributesFieldName.SESSION_ID] = session_id
    if _is_tracer_provider_set():
        tracer_provider: TracerProvider = trace.get_tracer_provider()
        for attr_key, attr_value in tracer_provider.resource.attributes.items():
            res_attrs[attr_key] = attr_value
    res_attrs[SpanResourceAttributesFieldName.SERVICE_NAME] = OTEL_RESOURCE_SERVICE_NAME
    if exp is not None:
        res_attrs[SpanResourceAttributesFieldName.EXPERIMENT_NAME] = exp
    if ws_triad is not None:
        res_attrs[SpanResourceAttributesFieldName.SUBSCRIPTION_ID] = ws_triad.subscription_id
        res_attrs[SpanResourceAttributesFieldName.RESOURCE_GROUP_NAME] = ws_triad.resource_group_name
        res_attrs[SpanResourceAttributesFieldName.WORKSPACE_NAME] = ws_triad.workspace_name
    return Resource(attributes=res_attrs)


def start_trace_with_devkit(
    session_id: typing.Optional[str],
    attrs: typing.Optional[typing.Dict[str, str]] = None,
    run: typing.Optional[str] = None,
) -> None:
    # honor and set attributes if user has specified
    if isinstance(attrs, dict):
        _inject_attrs_to_op_ctx(attrs)

    # experiment related attributes, pass from environment
    env_tracing_ctx = os.environ.get(PF_TRACE_CONTEXT, None)
    logger.debug("Read tracing context from environment: %s", env_tracing_ctx)
    env_attrs = dict(json.loads(env_tracing_ctx)).get(PF_TRACE_CONTEXT_ATTR) if env_tracing_ctx else dict()
    exp = env_attrs.get(ContextAttributeKey.EXPERIMENT, None)
    ref_line_run_id = env_attrs.get(ContextAttributeKey.REFERENCED_LINE_RUN_ID, None)
    op_ctx = OperationContext.get_instance()
    # remove `referenced.line_run_id` from context to avoid stale value set by previous node
    if ref_line_run_id is None:
        op_ctx._remove_otel_attributes(SpanAttributeFieldName.REFERENCED_LINE_RUN_ID)
    else:
        op_ctx._add_otel_attributes(SpanAttributeFieldName.REFERENCED_LINE_RUN_ID, ref_line_run_id)

    # local to cloud feature
    ws_triad = _get_ws_triad_from_pf_config()
    # invoke prompt flow service
    pfs_port = _invoke_pf_svc()

    _inject_res_attrs_to_environ(pfs_port=pfs_port, session_id=session_id, exp=exp, ws_triad=ws_triad)
    # instrument openai and setup exporter to pfs here for flex mode
    inject_openai_api()
    setup_exporter_to_pfs()
    # print tracing url(s)
    _print_tracing_url_from_local(pfs_port=pfs_port, session_id=session_id, exp=exp, run=run)
    _print_tracing_url_from_azure_portal(ws_triad=ws_triad, session_id=session_id, exp=exp, run=run)


def setup_exporter_to_pfs() -> None:
    # get resource attributes from environment
    session_id = os.getenv(TraceEnvironmentVariableName.SESSION_ID, None)
    exp = os.getenv(TraceEnvironmentVariableName.EXPERIMENT, None)
    # local to cloud scenario: workspace triad in resource.attributes
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
    # create resource, or merge to existing resource
    res = _create_or_merge_res(session_id=session_id, exp=exp, ws_triad=workspace_triad)
    tracer_provider = TracerProvider(resource=res)
    # get OTLP endpoint from environment
    endpoint = os.getenv(OTEL_EXPORTER_OTLP_ENDPOINT)
    if endpoint is not None:
        # create OTLP span exporter if endpoint is set
        otlp_span_exporter = OTLPSpanExporter(endpoint=endpoint)
        tracer_provider.add_span_processor(BatchSpanProcessor(otlp_span_exporter))
    # set tracer provider
    if _is_tracer_provider_set():
        _force_set_tracer_provider(tracer_provider)
    else:
        trace.set_tracer_provider(tracer_provider)
