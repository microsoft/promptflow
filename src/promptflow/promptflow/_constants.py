CONNECTION_NAME_PROPERTY = "__connection_name"
CONNECTION_SECRET_KEYS = "__secret_keys"
PROMPTFLOW_CONNECTIONS = "PROMPTFLOW_CONNECTIONS"
PROMPTFLOW_SECRETS_FILE = "PROMPTFLOW_SECRETS_FILE"
DEFAULT_FLOW_YAML_FILE = "flow.dag.yaml"
STORAGE_ACCOUNT_NAME = "STORAGE_ACCOUNT_NAME"
OPENAI_API_KEY = "openai-api-key"
BING_API_KEY = "bing-api-key"
AOAI_API_KEY = "aoai-api-key"
SERPAPI_API_KEY = "serpapi-api-key"
CONTENT_SAFETY_API_KEY = "content-safety-api-key"
TABLE_LIMIT_PROPERTY_SIZE = 64000  # 64 KB
TABLE_LIMIT_ENTITY_SIZE = 1000000  # 1 MB
SYNC_REQUEST_TIMEOUT_THRESHOLD = 10  # 10 seconds could be a normal timeout.
ERROR_RESPONSE_COMPONENT_NAME = "promptflow"
TOTAL_CHILD_RUNS_KEY = "total_child_runs"
PROMPTFLOW_EVAL_INFO_RELATIVE_PATH = "eval_info.json"
PROMPTFLOW_RUN_DETAILS_RELATIVE_PATH = "details.jsonl"


class AzureStorageType:
    LOCAL = "local"
    TABLE = "table"
    BLOB = "blob"


class AzureMLConfig:
    SUBSCRIPTION_ID = "SUBSCRIPTION_ID"
    RESOURCE_GROUP_NAME = "RESOURCE_GROUP_NAME"
    WORKSPACE_NAME = "WORKSPACE_NAME"
    MT_ENDPOINT = "MT_ENDPOINT"

    @classmethod
    def all_values(cls):
        all_values = []
        for key, value in vars(cls).items():
            if not key.startswith("_") and isinstance(value, str):
                all_values.append(value)
        return all_values


class PromptflowEdition:
    """Promptflow runtime edition."""

    COMMUNITY = "community"
    """Community edition."""
    ENTERPRISE = "enterprise"
    """Enterprise edition."""


class ComputeType:
    MANAGED_ONLINE_DEPLOYMENT = "managed_online_deployment"
    COMPUTE_INSTANCE = "compute_instance"
    LOCAL = "local"


class RuntimeMode:
    COMPUTE = "compute"
    SERVING = "serving"
