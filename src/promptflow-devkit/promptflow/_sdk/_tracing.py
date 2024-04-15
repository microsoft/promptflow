# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import typing

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.environment_variables import OTEL_EXPORTER_OTLP_ENDPOINT
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from promptflow._constants import (
    OTEL_RESOURCE_SERVICE_NAME,
    AzureWorkspaceKind,
    SpanAttributeFieldName,
    SpanResourceAttributesFieldName,
    TraceEnvironmentVariableName,
)
from promptflow._sdk._constants import (
    PF_TRACE_CONTEXT,
    PF_TRACE_CONTEXT_ATTR,
    AzureMLWorkspaceTriad,
    ContextAttributeKey,
)
from promptflow._sdk._service.utils.utils import (
    add_executable_script_to_env_path,
    get_port_from_config,
    hint_stop_before_upgrade,
    hint_stop_message,
    is_pfs_service_healthy,
    is_port_in_use,
    is_run_from_built_binary,
)
from promptflow._sdk._utils import extract_workspace_triad_from_trace_provider
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow.tracing._integrations._openai_injector import inject_openai_api
from promptflow.tracing._operation_context import OperationContext

_logger = get_cli_sdk_logger()

PF_CONFIG_TRACE_FEATURE_DISABLE = "none"
TRACER_PROVIDER_PFS_EXPORTER_SET_ATTR = "_pfs_exporter_set"


def is_trace_feature_disabled() -> bool:
    from promptflow._sdk._configuration import Configuration

    trace_provider = Configuration.get_instance().get_trace_provider()
    if isinstance(trace_provider, str):
        return Configuration.get_instance().get_trace_provider().lower() == PF_CONFIG_TRACE_FEATURE_DISABLE
    else:
        return False


def _is_azure_ext_installed() -> bool:
    try:
        importlib.metadata.version("promptflow-azure")
        return True
    except importlib.metadata.PackageNotFoundError:
        return False


def _get_collection_id_for_azure(collection: str) -> str:
    """{collection}_{object_id}"""
    import jwt

    from promptflow._cli._utils import get_credentials_for_cli
    from promptflow.azure._utils.general import get_arm_token

    token = get_arm_token(credential=get_credentials_for_cli())
    decoded_token = jwt.decode(token, options={"verify_signature": False})
    object_id = decoded_token["oid"]
    return f"{collection}_{object_id}"


def _inject_attrs_to_op_ctx(attrs: typing.Dict[str, str]) -> None:
    if len(attrs) == 0:
        return
    _logger.debug("inject attributes %s to context", attrs)
    op_ctx = OperationContext.get_instance()
    for attr_key, attr_value in attrs.items():
        op_ctx._add_otel_attributes(attr_key, attr_value)


def _invoke_pf_svc() -> str:
    port = get_port_from_config(create_if_not_exists=True)
    port = str(port)
    if is_run_from_built_binary():
        interpreter_path = os.path.abspath(sys.executable)
        pf_path = os.path.join(os.path.dirname(interpreter_path), "pf")
        cmd_args = [pf_path, "service", "start", "--port", port]
    else:
        cmd_args = ["pf", "service", "start", "--port", port]

    if is_port_in_use(int(port)):
        if not is_pfs_service_healthy(port):
            cmd_args.append("--force")
            _logger.debug("Prompt flow service is not healthy, force to start...")
        else:
            print("Prompt flow service has started...")
            return port

    add_executable_script_to_env_path()
    print("Starting prompt flow service...")
    start_pfs = None
    try:
        start_pfs = subprocess.Popen(cmd_args, shell=platform.system() == "Windows", stderr=subprocess.PIPE)
        # Wait for service to be started
        start_pfs.wait(timeout=20)
    except subprocess.TimeoutExpired:
        _logger.warning(
            f"The starting prompt flow process did not finish within the timeout period. {hint_stop_before_upgrade}"
        )
    except Exception as e:
        _logger.warning(f"An error occurred when starting prompt flow process: {e}. {hint_stop_before_upgrade}")

    # Check if there were any errors
    if start_pfs is not None and start_pfs.returncode is not None and start_pfs.returncode != 0:
        error_message = start_pfs.stderr.read().decode()
        message = f"The starting prompt flow process returned an error: {error_message}. "
        _logger.warning(message)
    elif not is_pfs_service_healthy(port):
        # this branch is to check if the service is healthy for msi installer
        _logger.warning(f"Prompt flow service is not healthy. {hint_stop_before_upgrade}")
    else:
        _logger.debug("Prompt flow service is serving on port %s", port)
        print(hint_stop_message)
    return port


def _get_ws_triad_from_pf_config() -> typing.Optional[AzureMLWorkspaceTriad]:
    from promptflow._sdk._configuration import Configuration

    ws_arm_id = Configuration.get_instance().get_trace_provider()
    return extract_workspace_triad_from_trace_provider(ws_arm_id) if ws_arm_id is not None else None


# priority: run > experiment > collection
# for run(s) in experiment, we should print url with run(s) as it is more specific;
# and url with experiment should be printed at the beginning of experiment start.
def _print_tracing_url_from_local(
    pfs_port: str,
    collection: str,
    exp: typing.Optional[str] = None,  # pylint: disable=unused-argument
    run: typing.Optional[str] = None,
) -> None:
    url = f"http://localhost:{pfs_port}/v1.0/ui/traces/"
    if run is not None:
        url += f"?#run={run}"
    else:
        # collection will not be None
        url += f"?#collection={collection}"
    print(f"You can view the traces from local: {url}")


def _print_tracing_url_from_azure_portal(
    ws_triad: AzureMLWorkspaceTriad,
    collection: str,
    exp: typing.Optional[str] = None,  # pylint: disable=unused-argument
    run: typing.Optional[str] = None,
) -> None:
    # as this there is an if condition for azure extension, we can assume the extension is installed
    from azure.ai.ml import MLClient

    from promptflow._cli._utils import get_credentials_for_cli

    # we have different url for Azure ML workspace and AI project
    # so we need to distinguish them
    ml_client = MLClient(
        credential=get_credentials_for_cli(),
        subscription_id=ws_triad.subscription_id,
        resource_group_name=ws_triad.resource_group_name,
        workspace_name=ws_triad.workspace_name,
    )
    workspace = ml_client.workspaces.get(name=ws_triad.workspace_name)

    url = (
        "https://int.ml.azure.com/{query}?"
        f"wsid=/subscriptions/{ws_triad.subscription_id}"
        f"/resourceGroups/{ws_triad.resource_group_name}"
        "/providers/Microsoft.MachineLearningServices"
        f"/workspaces/{ws_triad.workspace_name}"
        "&flight=PFTrace,PFNewRunDetail"
    )

    if run is None:
        _logger.debug("run is not specified, need to concat `collection_id` for query")
        collection_id = _get_collection_id_for_azure(collection=collection)
    if AzureWorkspaceKind.is_workspace(workspace):
        _logger.debug(f"{ws_triad.workspace_name!r} is an Azure ML workspace.")
        if run is None:
            query = f"trace/collection/{collection_id}/list"
        else:
            query = f"prompts/trace/run/{run}/details"
    elif AzureWorkspaceKind.is_project(workspace):
        _logger.debug(f"{ws_triad.workspace_name!r} is an Azure AI project.")
        url = url.replace("int.ml.azure.com", "int.ai.azure.com")
        if run is None:
            query = f"projecttrace/collection/{collection_id}/list"
        else:
            query = f"projectflows/trace/run/{run}/details"
    else:
        _logger.error(f"the workspace type of {ws_triad.workspace_name!r} is not supported.")
        return

    url = url.format(query=query)
    print(f"You can view the traces in cloud from Azure portal: {url}")


def _inject_res_attrs_to_environ(
    pfs_port: str,
    collection: str,
    exp: typing.Optional[str] = None,
    ws_triad: typing.Optional[AzureMLWorkspaceTriad] = None,
) -> None:
    _logger.debug("set collection to environ: %s", collection)
    os.environ[TraceEnvironmentVariableName.COLLECTION] = collection
    if exp is not None:
        _logger.debug("set experiment to environ: %s", exp)
        os.environ[TraceEnvironmentVariableName.EXPERIMENT] = exp
    if ws_triad is not None:
        _logger.debug(
            "set workspace triad to environ: %s, %s, %s",
            ws_triad.subscription_id,
            ws_triad.resource_group_name,
            ws_triad.workspace_name,
        )
        os.environ[TraceEnvironmentVariableName.SUBSCRIPTION_ID] = ws_triad.subscription_id
        os.environ[TraceEnvironmentVariableName.RESOURCE_GROUP_NAME] = ws_triad.resource_group_name
        os.environ[TraceEnvironmentVariableName.WORKSPACE_NAME] = ws_triad.workspace_name
    # we will not overwrite the value if it is already set
    if OTEL_EXPORTER_OTLP_ENDPOINT not in os.environ:
        otlp_endpoint = f"http://localhost:{pfs_port}/v1/traces"
        _logger.debug("set OTLP endpoint to environ: %s", otlp_endpoint)
        os.environ[OTEL_EXPORTER_OTLP_ENDPOINT] = otlp_endpoint


def _create_res(
    collection: typing.Optional[str],
    collection_id: typing.Optional[str] = None,
    exp: typing.Optional[str] = None,
    ws_triad: typing.Optional[AzureMLWorkspaceTriad] = None,
) -> Resource:
    res_attrs = dict()
    if collection is not None:
        res_attrs[SpanResourceAttributesFieldName.COLLECTION] = collection
    if collection_id is not None:
        res_attrs[SpanResourceAttributesFieldName.COLLECTION_ID] = collection_id
    res_attrs[SpanResourceAttributesFieldName.SERVICE_NAME] = OTEL_RESOURCE_SERVICE_NAME
    if exp is not None:
        res_attrs[SpanResourceAttributesFieldName.EXPERIMENT_NAME] = exp
    if ws_triad is not None:
        res_attrs[SpanResourceAttributesFieldName.SUBSCRIPTION_ID] = ws_triad.subscription_id
        res_attrs[SpanResourceAttributesFieldName.RESOURCE_GROUP_NAME] = ws_triad.resource_group_name
        res_attrs[SpanResourceAttributesFieldName.WORKSPACE_NAME] = ws_triad.workspace_name
    return Resource(attributes=res_attrs)


def start_trace_with_devkit(collection: str, **kwargs: typing.Any) -> None:
    if is_trace_feature_disabled():
        _logger.info("trace feature is disabled in config, skip setup exporter to PFS.")
        return

    _logger.debug("collection: %s", collection)
    _logger.debug("kwargs: %s", kwargs)
    attrs = kwargs.get("attributes", None)
    run = kwargs.get("run", None)

    # honor and set attributes if user has specified
    if isinstance(attrs, dict):
        _inject_attrs_to_op_ctx(attrs)
    # set session id if specified
    # this is exclusive concept in chat experience with UX
    session_id = kwargs.get("session", None)
    if session_id is not None:
        _inject_attrs_to_op_ctx({SpanAttributeFieldName.SESSION_ID: session_id})

    # experiment related attributes, pass from environment
    env_tracing_ctx = os.environ.get(PF_TRACE_CONTEXT, None)
    _logger.debug("read tracing context from environment: %s", env_tracing_ctx)
    env_attrs = dict(json.loads(env_tracing_ctx)).get(PF_TRACE_CONTEXT_ATTR) if env_tracing_ctx else dict()
    exp = env_attrs.get(ContextAttributeKey.EXPERIMENT, None)
    ref_line_run_id = env_attrs.get(ContextAttributeKey.REFERENCED_LINE_RUN_ID, None)
    op_ctx = OperationContext.get_instance()
    # remove `referenced.line_run_id` from context to avoid stale value set by previous node
    if ref_line_run_id is None:
        op_ctx._remove_otel_attributes(SpanAttributeFieldName.REFERENCED_LINE_RUN_ID)
    else:
        op_ctx._add_otel_attributes(SpanAttributeFieldName.REFERENCED_LINE_RUN_ID, ref_line_run_id)
    _logger.debug("operation context OTel attributes: %s", op_ctx._get_otel_attributes())

    # local to cloud feature
    ws_triad = _get_ws_triad_from_pf_config()
    is_azure_ext_installed = _is_azure_ext_installed()
    if ws_triad is not None and not is_azure_ext_installed:
        warning_msg = (
            "Azure extension is not installed, though export to cloud is configured, "
            "traces cannot be exported to cloud. To fix this, please run `pip install promptflow-azure` "
            "and restart prompt flow service."
        )
        _logger.warning(warning_msg)

    # invoke prompt flow service
    pfs_port = _invoke_pf_svc()
    is_pfs_healthy = is_pfs_service_healthy(pfs_port)
    if not is_pfs_healthy:
        warning_msg = (
            "Prompt flow service is not healthy, please check the logs for more details; "
            "traces might not be exported correctly."
        )
        _logger.warning(warning_msg)
        return

    _inject_res_attrs_to_environ(pfs_port=pfs_port, collection=collection, exp=exp, ws_triad=ws_triad)
    # instrument openai and setup exporter to pfs here for flex mode
    inject_openai_api()
    setup_exporter_to_pfs()
    # print tracing url(s)
    _print_tracing_url_from_local(pfs_port=pfs_port, collection=collection, exp=exp, run=run)
    if ws_triad is not None and is_azure_ext_installed:
        _print_tracing_url_from_azure_portal(ws_triad=ws_triad, collection=collection, exp=exp, run=run)


def setup_exporter_to_pfs() -> None:
    if is_trace_feature_disabled():
        _logger.info("trace feature is disabled in config, skip setup exporter to PFS.")
        return

    _logger.debug("start setup exporter to prompt flow service...")
    # get resource attributes from environment
    # For local trace, collection is the only identifier for name and id
    # For cloud trace, we use collection here as name and collection_id for id
    collection = os.getenv(TraceEnvironmentVariableName.COLLECTION, None)
    _logger.debug("collection from environ: %s", collection)
    # Only used for runtime
    collection_id = os.getenv(TraceEnvironmentVariableName.COLLECTION_ID, None)
    _logger.debug("collection_id from environ: %s", collection_id)
    exp = os.getenv(TraceEnvironmentVariableName.EXPERIMENT, None)
    _logger.debug("experiment from environ: %s", exp)
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
    # tracer provider
    # create resource & tracer provider, or merge resource
    res = _create_res(collection=collection, collection_id=collection_id, exp=exp, ws_triad=workspace_triad)
    _logger.debug("resource attributes: %s", res.attributes)
    cur_tracer_provider = trace.get_tracer_provider()
    if isinstance(cur_tracer_provider, TracerProvider):
        _logger.info("tracer provider is already set, will merge the resource attributes...")
        cur_res: Resource = cur_tracer_provider.resource
        _logger.debug("current resource: %s", cur_res.attributes)
        new_res = cur_res.merge(res)
        cur_tracer_provider._resource = new_res
        _logger.info("tracer provider is updated with resource attributes: %s", new_res.attributes)
    else:
        tracer_provider = TracerProvider(resource=res)
        trace.set_tracer_provider(tracer_provider)
        _logger.info("tracer provider is set with resource attributes: %s", res.attributes)
    # set exporter to PFS
    # get OTLP endpoint from environment
    endpoint = os.getenv(OTEL_EXPORTER_OTLP_ENDPOINT)
    _logger.debug("environ OTEL_EXPORTER_OTLP_ENDPOINT: %s", endpoint)
    if endpoint is not None:
        # create OTLP span exporter if endpoint is set
        otlp_span_exporter = OTLPSpanExporter(endpoint=endpoint)
        tracer_provider: TracerProvider = trace.get_tracer_provider()
        if not getattr(tracer_provider, TRACER_PROVIDER_PFS_EXPORTER_SET_ATTR, False):
            _logger.info("have not set exporter to prompt flow service, will set it...")
            tracer_provider.add_span_processor(BatchSpanProcessor(otlp_span_exporter))
            setattr(tracer_provider, TRACER_PROVIDER_PFS_EXPORTER_SET_ATTR, True)
        else:
            _logger.info("exporter to prompt flow service is already set, no action needed.")
    _logger.debug("finish setup exporter to prompt flow service.")
