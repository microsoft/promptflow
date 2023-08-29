# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
__path__ = __import__("pkgutil").extend_path(__path__, __name__)  # type: ignore

# flake8: noqa

"""Put some imports here for internal packages to minimize the effort of refactoring."""
from promptflow._constants import PROMPTFLOW_CONNECTIONS
from promptflow._core._errors import GenerateMetaUserError, PackageToolNotFoundError, ToolExecutionError
from promptflow._core.cache_manager import AbstractCacheManager, CacheManager, enable_cache
from promptflow._core.connection_manager import ConnectionManager
from promptflow._core.flow_execution_context import FlowExecutionContext
from promptflow._core.log_manager import NodeLogManager, NodeLogWriter
from promptflow._core.metric_logger import add_metric_logger
from promptflow._core.openai_injector import inject_openai_api
from promptflow._core.operation_context import OperationContext
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
    ToolsLoader,
    ToolsManager,
    builtins,
    collect_package_tools,
    register_apis,
    register_builtins,
    register_connections,
)
from promptflow._core.tracer import Tracer
from promptflow._sdk._constants import LOCAL_MGMT_DB_PATH
from promptflow._sdk._serving.response_creator import ResponseCreator
from promptflow._sdk._serving.swagger import generate_swagger
from promptflow._sdk._serving.utils import (
    get_output_fields_to_remove,
    get_sample_json,
    handle_error_to_response,
    load_request_data,
    streaming_response_required,
    validate_request_data,
)
from promptflow._sdk._utils import (
    get_used_connection_names_from_environment_variables,
    setup_user_agent_to_operation_context,
    update_environment_variables_with_connections,
)
from promptflow._utils.context_utils import _change_working_dir, inject_sys_path
from promptflow._utils.credential_scrubber import CredentialScrubber
from promptflow._utils.dataclass_serializer import deserialize_dataclass, serialize
from promptflow._utils.exception_utils import (
    ErrorResponse,
    ExceptionPresenter,
    JsonSerializedPromptflowException,
    RootErrorCode,
    infer_error_code_from_class,
)
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
from promptflow._utils.utils import (
    AttrDict,
    camel_to_snake,
    count_and_log_progress,
    load_json,
    reverse_transpose,
    set_context,
    transpose,
)
from promptflow._version import VERSION
from promptflow.executor._errors import InputNotFound
