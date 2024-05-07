# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
__path__ = __import__("pkgutil").extend_path(__path__, __name__)  # type: ignore

# flake8: noqa

"""Put some imports here for internal packages to minimize the effort of refactoring."""
from promptflow._constants import (
    PROMPTFLOW_CONNECTIONS,
    CosmosDBContainerName,
    SpanAttributeFieldName,
    TraceEnvironmentVariableName,
)
from promptflow._core._errors import GenerateMetaUserError, PackageToolNotFoundError, ToolExecutionError
from promptflow._core.cache_manager import AbstractCacheManager, CacheManager, enable_cache
from promptflow._core.connection_manager import ConnectionManager
from promptflow._core.entry_meta_generator import generate_flow_meta
from promptflow._core.flow_execution_context import FlowExecutionContext
from promptflow._core.log_manager import NodeLogManager, NodeLogWriter
from promptflow._core.metric_logger import add_metric_logger
from promptflow._core.run_tracker import RunRecordNotFound, RunTracker
from promptflow._core.tool import ToolInvoker, ToolProvider, tool
from promptflow._core.tool_meta_generator import (
    JinjaParsingError,
    MultipleToolsDefined,
    NoToolDefined,
    PythonParsingError,
    ReservedVariableCannotBeUsed,
    generate_prompt_meta,
    generate_python_meta,
    generate_tool_meta_dict_by_file,
    is_tool,
)
from promptflow._core.tools_manager import (
    BuiltinsManager,
    CustomPythonToolLoadError,
    EmptyCodeInCustomTool,
    MissingTargetFunction,
    ToolsManager,
    builtins,
    collect_package_tools,
    register_apis,
    register_builtins,
    register_connections,
    retrieve_tool_func_result,
)
from promptflow._proxy import ProxyFactory
from promptflow._proxy._base_executor_proxy import APIBasedExecutorProxy
from promptflow._proxy._csharp_executor_proxy import CSharpBaseExecutorProxy
from promptflow._sdk._constants import LOCAL_MGMT_DB_PATH, CreatedByFieldName
from promptflow._sdk._service.apis.collector import trace_collector
from promptflow._sdk._tracing import process_otlp_trace_request
from promptflow._sdk._utilities.general_utils import resolve_flow_language
from promptflow._sdk._utilities.tracing_utils import aggregate_trace_count
from promptflow._sdk._version import VERSION
from promptflow._utils.context_utils import _change_working_dir, inject_sys_path
from promptflow._utils.credential_scrubber import CredentialScrubber
from promptflow._utils.dataclass_serializer import deserialize_dataclass
from promptflow._utils.exception_utils import (
    ErrorResponse,
    ExceptionPresenter,
    JsonSerializedPromptflowException,
    RootErrorCode,
    infer_error_code_from_class,
)
from promptflow._utils.execution_utils import handle_line_failures
from promptflow._utils.feature_utils import Feature, FeatureState, get_feature_list
from promptflow._utils.inputs_mapping_utils import apply_inputs_mapping
from promptflow._utils.logger_utils import (
    DATETIME_FORMAT,
    LOG_FORMAT,
    CredentialScrubberFormatter,
    FileHandler,
    FileHandlerConcurrentWrapper,
    LogContext,
    bulk_logger,
    flow_logger,
    get_logger,
    logger,
    update_log_path,
)
from promptflow._utils.multimedia_data_converter import (
    AbstractMultimediaInfoConverter,
    MultimediaConverter,
    MultimediaInfo,
    ResourceType,
)
from promptflow._utils.multimedia_utils import (
    MultimediaProcessor,
    load_multimedia_data_recursively,
    persist_multimedia_data,
    resolve_multimedia_data_recursively,
)
from promptflow._utils.user_agent_utils import setup_user_agent_to_operation_context
from promptflow._utils.utils import (
    AttrDict,
    camel_to_snake,
    count_and_log_progress,
    load_json,
    reverse_transpose,
    set_context,
    transpose,
)
from promptflow.core._connection_provider._workspace_connection_provider import WorkspaceConnectionProvider
from promptflow.core._errors import OpenURLNotFoundError
from promptflow.core._serving.response_creator import ResponseCreator
from promptflow.core._serving.swagger import generate_swagger
from promptflow.core._serving.utils import (
    get_output_fields_to_remove,
    get_sample_json,
    load_request_data,
    validate_request_data,
)
from promptflow.core._serving.v1.utils import handle_error_to_response, streaming_response_required
from promptflow.core._utils import (
    get_used_connection_names_from_dict,
    get_used_connection_names_from_environment_variables,
    update_dict_value_with_connections,
    update_environment_variables_with_connections,
)
from promptflow.executor._errors import InputNotFound
from promptflow.executor._tool_invoker import DefaultToolInvoker
from promptflow.storage._run_storage import DefaultRunStorage
from promptflow.tracing._constants import PF_TRACING_SKIP_LOCAL_SETUP_ENVIRON
from promptflow.tracing._integrations._openai_injector import inject_openai_api
from promptflow.tracing._operation_context import OperationContext
from promptflow.tracing._start_trace import setup_exporter_from_environ
from promptflow.tracing._tracer import Tracer
from promptflow.tracing._utils import serialize
