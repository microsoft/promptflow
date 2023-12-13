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
