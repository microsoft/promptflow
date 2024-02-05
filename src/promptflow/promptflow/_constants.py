# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

CONNECTION_NAME_PROPERTY = "__connection_name"
CONNECTION_SECRET_KEYS = "__secret_keys"
PROMPTFLOW_CONNECTIONS = "PROMPTFLOW_CONNECTIONS"
PROMPTFLOW_SECRETS_FILE = "PROMPTFLOW_SECRETS_FILE"
PF_NO_INTERACTIVE_LOGIN = "PF_NO_INTERACTIVE_LOGIN"
PF_LOGGING_LEVEL = "PF_LOGGING_LEVEL"
OPENAI_API_KEY = "openai-api-key"
BING_API_KEY = "bing-api-key"
AOAI_API_KEY = "aoai-api-key"
SERPAPI_API_KEY = "serpapi-api-key"
CONTENT_SAFETY_API_KEY = "content-safety-api-key"
ERROR_RESPONSE_COMPONENT_NAME = "promptflow"
EXTENSION_UA = "prompt-flow-extension"
LANGUAGE_KEY = "language"

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


class SpanAttributeFieldName:
    FRAMEWORK = "framework"
    SPAN_TYPE = "span_type"
    FUNCTION = "function"
    INPUTS = "inputs"
    OUTPUT = "output"
    SESSION_ID = "session_id"
    PATH = "path"
    FLOW_ID = "flow_id"
    RUN = "run"
    EXPERIMENT = "experiment"
    LINE_RUN_ID = "line_run_id"
    REFERENCED_LINE_RUN_ID = "referenced.line_run_id"
    COMPLETION_TOKEN_COUNT = "__computed__.cumulative_token_count.completion"
    PROMPT_TOKEN_COUNT = "__computed__.cumulative_token_count.prompt"
    TOTAL_TOKEN_COUNT = "__computed__.cumulative_token_count.total"


class SpanResourceAttributesFieldName:
    SERVICE_NAME = "service.name"


class SpanResourceFieldName:
    ATTRIBUTES = "attributes"
    SCHEMA_URL = "schema_url"


DEFAULT_SESSION_ID = "default"
DEFAULT_SPAN_TYPE = "default"
