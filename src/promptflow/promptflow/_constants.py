# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path

CONNECTION_NAME_PROPERTY = "__connection_name"
CONNECTION_SECRET_KEYS = "__secret_keys"
PROMPTFLOW_CONNECTIONS = "PROMPTFLOW_CONNECTIONS"
PROMPTFLOW_SECRETS_FILE = "PROMPTFLOW_SECRETS_FILE"
PF_NO_INTERACTIVE_LOGIN = "PF_NO_INTERACTIVE_LOGIN"
PF_RUN_AS_BUILT_BINARY = "PF_RUN_AS_BUILT_BINARY"
PF_LOGGING_LEVEL = "PF_LOGGING_LEVEL"
OPENAI_API_KEY = "openai-api-key"
BING_API_KEY = "bing-api-key"
AOAI_API_KEY = "aoai-api-key"
SERPAPI_API_KEY = "serpapi-api-key"
CONTENT_SAFETY_API_KEY = "content-safety-api-key"
ERROR_RESPONSE_COMPONENT_NAME = "promptflow"
EXTENSION_UA = "prompt-flow-extension"
LANGUAGE_KEY = "language"
USER_AGENT_OVERRIDE_KEY = "user_agent_override"

# Tool meta info
ICON_DARK = "icon_dark"
ICON_LIGHT = "icon_light"
ICON = "icon"
UIONLY_HIDDEN = "uionly_hidden"
SKIP_FUNC_PARAMS = ["subscription_id", "resource_group_name", "workspace_name"]
TOOL_SCHEMA = Path(__file__).parent / "_sdk" / "data" / "tool.schema.json"
PF_MAIN_MODULE_NAME = "__pf_main__"

DEFAULT_ENCODING = "utf-8"

# Constants related to execution
LINE_NUMBER_KEY = "line_number"  # Using the same key with portal.
LINE_TIMEOUT_SEC = 600


class FlowLanguage:
    """The enum of tool source type."""

    Python = "python"
    CSharp = "csharp"


class AvailableIDE:
    VS = "vs"
    VS_CODE = "vsc"


USER_AGENT = "USER_AGENT"
PF_USER_AGENT = "PF_USER_AGENT"

CLI_PACKAGE_NAME = "promptflow"
CURRENT_VERSION = "current_version"
LATEST_VERSION = "latest_version"
LAST_HINT_TIME = "last_hint_time"
LAST_CHECK_TIME = "last_check_time"
PF_VERSION_CHECK = "pf_version_check.json"
HINT_INTERVAL_DAY = 7
GET_PYPI_INTERVAL_DAY = 7

_ENV_PF_INSTALLER = "PF_INSTALLER"
STREAMING_ANIMATION_TIME = 0.01

# trace related
OTEL_RESOURCE_SERVICE_NAME = "promptflow"
DEFAULT_SPAN_TYPE = "default"


class TraceEnvironmentVariableName:
    EXPERIMENT = "PF_TRACE_EXPERIMENT"
    SESSION_ID = "PF_TRACE_SESSION_ID"
    SUBSCRIPTION_ID = "PF_TRACE_SUBSCRIPTION_ID"
    RESOURCE_GROUP_NAME = "PF_TRACE_RESOURCE_GROUP_NAME"
    WORKSPACE_NAME = "PF_TRACE_WORKSPACE_NAME"


class CosmosDBContainerName:
    SPAN = "Span"
    LINE_SUMMARY = "LineSummary"


class SpanFieldName:
    NAME = "name"
    CONTEXT = "context"
    KIND = "kind"
    PARENT_ID = "parent_id"
    START_TIME = "start_time"
    END_TIME = "end_time"
    STATUS = "status"
    ATTRIBUTES = "attributes"
    EVENTS = "events"
    LINKS = "links"
    RESOURCE = "resource"


class SpanContextFieldName:
    TRACE_ID = "trace_id"
    SPAN_ID = "span_id"
    TRACE_STATE = "trace_state"


class SpanStatusFieldName:
    STATUS_CODE = "status_code"
    DESCRIPTION = "description"


class SpanAttributeFieldName:
    FRAMEWORK = "framework"
    SPAN_TYPE = "span_type"
    FUNCTION = "function"
    INPUTS = "inputs"
    OUTPUT = "output"
    # token metrics
    COMPLETION_TOKEN_COUNT = "llm.usage.completion_tokens"
    PROMPT_TOKEN_COUNT = "llm.usage.prompt_tokens"
    TOTAL_TOKEN_COUNT = "llm.usage.total_tokens"
    CUMULATIVE_COMPLETION_TOKEN_COUNT = "__computed__.cumulative_token_count.completion"
    CUMULATIVE_PROMPT_TOKEN_COUNT = "__computed__.cumulative_token_count.prompt"
    CUMULATIVE_TOTAL_TOKEN_COUNT = "__computed__.cumulative_token_count.total"
    # test
    LINE_RUN_ID = "line_run_id"
    REFERENCED_LINE_RUN_ID = "referenced.line_run_id"
    BATCH_RUN_ID = "batch_run_id"
    LINE_NUMBER = "line_number"
    REFERENCED_BATCH_RUN_ID = "referenced.batch_run_id"
    COMPLETION_TOKEN_COUNT = "__computed__.cumulative_token_count.completion"
    PROMPT_TOKEN_COUNT = "__computed__.cumulative_token_count.prompt"
    TOTAL_TOKEN_COUNT = "__computed__.cumulative_token_count.total"


class SpanResourceAttributesFieldName:
    SERVICE_NAME = "service.name"
    SESSION_ID = "session.id"
    EXPERIMENT_NAME = "experiment.name"
    # local to cloud
    SUBSCRIPTION_ID = "subscription.id"
    RESOURCE_GROUP_NAME = "resource_group.name"
    WORKSPACE_NAME = "workspace.name"
    # batch run
    BATCH_RUN_ID = "batch_run_id"
    LINE_NUMBER = "line_number"
    REFERENCED_BATCH_RUN_ID = "referenced.batch_run_id"


class SpanResourceFieldName:
    ATTRIBUTES = "attributes"
    SCHEMA_URL = "schema_url"


class SpanEventFieldName:
    NAME = "name"
    TIMESTAMP = "timestamp"
    ATTRIBUTES = "attributes"


class SpanLinkFieldName:
    CONTEXT = "context"
    ATTRIBUTES = "attributes"


class MessageFormatType:
    BASIC = "basic"
    OPENAI_VISION = "openai_vision"


DEFAULT_OUTPUT_NAME = "output"

OUTPUT_FILE_NAME = "output.jsonl"


class OutputsFolderName:
    FLOW_OUTPUTS = "flow_outputs"
    FLOW_ARTIFACTS = "flow_artifacts"
    NODE_ARTIFACTS = "node_artifacts"
