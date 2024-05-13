# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from enum import Enum
from pathlib import Path

CONNECTION_NAME_PROPERTY = "__connection_name"
CONNECTION_SECRET_KEYS = "__secret_keys"
CONNECTION_SCRUBBED_VALUE = "******"
CONNECTION_SCRUBBED_VALUE_NO_CHANGE = "<no-change>"
PROMPTFLOW_CONNECTIONS = "PROMPTFLOW_CONNECTIONS"
PROMPTFLOW_SECRETS_FILE = "PROMPTFLOW_SECRETS_FILE"
PF_NO_INTERACTIVE_LOGIN = "PF_NO_INTERACTIVE_LOGIN"
PF_RUN_AS_BUILT_BINARY = "PF_RUN_AS_BUILT_BINARY"
PF_FLOW_INIT_CONFIG = "PF_FLOW_INIT_CONFIG"
ENABLE_MULTI_CONTAINER_KEY = "PF_ENABLE_MULTI_CONTAINER"
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

FLOW_DAG_YAML = "flow.dag.yaml"
FLOW_FLEX_YAML = "flow.flex.yaml"
PROMPTY_EXTENSION = ".prompty"
FLOW_FILE_SUFFIX = (".yaml", ".yml", PROMPTY_EXTENSION)

CHAT_HISTORY = "chat_history"

# Tool meta info
ICON_DARK = "icon_dark"
ICON_LIGHT = "icon_light"
ICON = "icon"
UIONLY_HIDDEN = "uionly_hidden"
SKIP_FUNC_PARAMS = ["subscription_id", "resource_group_name", "workspace_name"]
TOOL_SCHEMA = Path(__file__).parent / "_core" / "data" / "tool.schema.json"
PF_MAIN_MODULE_NAME = "__pf_main__"

DEFAULT_ENCODING = "utf-8"
FLOW_META_JSON = "flow.json"
FLOW_META_JSON_GEN_TIMEOUT = 60
PROMPT_FLOW_DIR_NAME = ".promptflow"
FLOW_TOOLS_JSON = "flow.tools.json"

# Constants related to execution
LINE_NUMBER_KEY = "line_number"  # Using the same key with portal.
# Fill zero to the left of line number to make it 9 digits. This is to make sure the line number file name is sortable.
LINE_NUMBER_WIDTH = 9
LINE_TIMEOUT_SEC = 600

# Environment variables
PF_LONG_RUNNING_LOGGING_INTERVAL = "PF_LONG_RUNNING_LOGGING_INTERVAL"


class FlowLanguage:
    """The enum of tool source type."""

    Python = "python"
    CSharp = "csharp"


class FlowEntryRegex:
    """The regex pattern for flow entry function."""

    Python = r"^[a-zA-Z0-9_.]+:[a-zA-Z0-9_]+$"
    CSharp = r"\((.+)\)[a-zA-Z0-9]+(\.[a-zA-Z0-9]+)+"


class FlowType:
    """The enum of flow type."""

    DAG_FLOW = "dag"
    FLEX_FLOW = "flex"
    PROMPTY = "prompty"


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
RUNNING_LINE_RUN_STATUS = "Running"
OK_LINE_RUN_STATUS = "Ok"
SPAN_EVENTS_ATTRIBUTES_EVENT_ID = "event.id"


class TraceEnvironmentVariableName:
    EXPERIMENT = "PF_TRACE_EXPERIMENT"
    COLLECTION = "PF_TRACE_COLLECTION"
    SESSION_ID = "PF_TRACE_SESSION_ID"  # will be deprecated
    COLLECTION_ID = "PF_TRACE_COLLECTION_ID"
    SUBSCRIPTION_ID = "PF_TRACE_SUBSCRIPTION_ID"
    RESOURCE_GROUP_NAME = "PF_TRACE_RESOURCE_GROUP_NAME"
    WORKSPACE_NAME = "PF_TRACE_WORKSPACE_NAME"


class CosmosDBContainerName:
    SPAN = "Span"
    LINE_SUMMARY = "LineSummary"
    COLLECTION = "Collection"


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
    EXTERNAL_EVENT_DATA_URIS = "external_event_data_uris"


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
    IS_AGGREGATION = "is_aggregation"
    COMPLETION_TOKEN_COUNT = "__computed__.cumulative_token_count.completion"
    PROMPT_TOKEN_COUNT = "__computed__.cumulative_token_count.prompt"
    TOTAL_TOKEN_COUNT = "__computed__.cumulative_token_count.total"
    # Execution target, e.g. prompty, flex, dag, code.
    # We may need another field to indicate the language, e.g. python, csharp.
    EXECUTION_TARGET = "execution_target"

    SESSION_ID = "session_id"


class SpanResourceAttributesFieldName:
    SERVICE_NAME = "service.name"
    SESSION_ID = "session.id"
    COLLECTION = "collection"  # local
    COLLECTION_ID = "collection.id"  # cloud & local to cloud
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
    OPENAI_VISION = "openai-vision"


DEFAULT_OUTPUT_NAME = "output"
OUTPUT_FILE_NAME = "output.jsonl"


class OutputsFolderName:
    FLOW_OUTPUTS = "flow_outputs"
    FLOW_ARTIFACTS = "flow_artifacts"
    NODE_ARTIFACTS = "node_artifacts"


class ConnectionType(str, Enum):
    _NOT_SET = "NotSet"
    AZURE_OPEN_AI = "AzureOpenAI"
    OPEN_AI = "OpenAI"
    QDRANT = "Qdrant"
    COGNITIVE_SEARCH = "CognitiveSearch"
    SERP = "Serp"
    AZURE_CONTENT_SAFETY = "AzureContentSafety"
    AZURE_AI_SERVICES = "AzureAIServices"
    FORM_RECOGNIZER = "FormRecognizer"
    WEAVIATE = "Weaviate"
    SERVERLESS = "Serverless"
    CUSTOM = "Custom"


class CustomStrongTypeConnectionConfigs:
    PREFIX = "promptflow.connection."
    TYPE = "custom_type"
    MODULE = "module"
    PACKAGE = "package"
    PACKAGE_VERSION = "package_version"
    PROMPTFLOW_TYPE_KEY = PREFIX + TYPE
    PROMPTFLOW_MODULE_KEY = PREFIX + MODULE
    PROMPTFLOW_PACKAGE_KEY = PREFIX + PACKAGE
    PROMPTFLOW_PACKAGE_VERSION_KEY = PREFIX + PACKAGE_VERSION

    @staticmethod
    def is_custom_key(key):
        return key not in [
            CustomStrongTypeConnectionConfigs.PROMPTFLOW_TYPE_KEY,
            CustomStrongTypeConnectionConfigs.PROMPTFLOW_MODULE_KEY,
            CustomStrongTypeConnectionConfigs.PROMPTFLOW_PACKAGE_KEY,
            CustomStrongTypeConnectionConfigs.PROMPTFLOW_PACKAGE_VERSION_KEY,
        ]


class TokenKeys:
    TOTAL_TOKENS = "total_tokens"
    COMPLETION_TOKENS = "completion_tokens"
    PROMPT_TOKENS = "prompt_tokens"

    @staticmethod
    def get_all_values():
        values = [value for key, value in vars(TokenKeys).items() if isinstance(value, str) and key.isupper()]
        return values


class SystemMetricKeys:
    NODE_PREFIX = "__pf__.nodes"
    LINES_COMPLETED = "__pf__.lines.completed"
    LINES_FAILED = "__pf__.lines.failed"


class ConnectionProviderConfig:
    LOCAL = "local"
    AZUREML = "azureml"


AZURE_WORKSPACE_REGEX_FORMAT = (
    "^azureml:[/]{1,2}subscriptions/([^/]+)/resource(groups|Groups)/([^/]+)"
    "(/providers/Microsoft.MachineLearningServices)?/workspaces/([^/]+)$"
)
CONNECTION_DATA_CLASS_KEY = "DATA_CLASS"
AML_WORKSPACE_TEMPLATE = "azureml://subscriptions/{}/resourceGroups/{}/providers/Microsoft.MachineLearningServices/workspaces/{}"  # noqa: E501


class AzureWorkspaceKind:
    DEFAULT = "default"
    HUB = "hub"
    PROJECT = "project"

    # obj can be string or azure.ai.ml.entities.Workspace
    @staticmethod
    def is_workspace(obj) -> bool:
        if isinstance(obj, str):
            return obj == AzureWorkspaceKind.DEFAULT
        return obj._kind == AzureWorkspaceKind.DEFAULT

    @staticmethod
    def is_hub(obj) -> bool:
        if isinstance(obj, str):
            return obj == AzureWorkspaceKind.HUB
        return obj._kind == AzureWorkspaceKind.HUB

    @staticmethod
    def is_project(obj) -> bool:
        if isinstance(obj, str):
            return obj == AzureWorkspaceKind.PROJECT
        return obj._kind == AzureWorkspaceKind.PROJECT
