# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from enum import Enum
from pathlib import Path

LOGGER_NAME = "promptflow"

DAG_FILE_NAME = "flow.dag.yaml"
NODE_VARIANTS = "node_variants"
VARIANTS = "variants"
NODES = "nodes"
NODE = "node"
INPUTS = "inputs"
USE_VARIANTS = "use_variants"
DEFAULT_VAR_ID = "default_variant_id"
FLOW_TOOLS_JSON = "flow.tools.json"

HOME_PROMPT_FLOW_DIR = (Path.home() / ".promptflow").resolve()
if not HOME_PROMPT_FLOW_DIR.is_dir():
    HOME_PROMPT_FLOW_DIR.mkdir(exist_ok=True)

LOCAL_MGMT_DB_PATH = (HOME_PROMPT_FLOW_DIR / "pf.sqlite").resolve()
LOCAL_MGMT_DB_SESSION_ACQUIRE_LOCK_PATH = (
    HOME_PROMPT_FLOW_DIR / "pf.sqlite.lock"
).resolve()
SCHEMA_INFO_TABLENAME = "schema_info"
RUN_INFO_TABLENAME = "run_info"
RUN_INFO_CREATED_ON_INDEX_NAME = "idx_run_info_created_on"
CONNECTION_TABLE_NAME = "connection"
BASE_PATH_CONTEXT_KEY = "base_path"
PARAMS_OVERRIDE_KEY = "params_override"
FILE_PREFIX = "file:"
KEYRING_SYSTEM = "promptflow"
KEYRING_ENCRYPTION_KEY_NAME = "encryption_key"
KEYRING_ENCRYPTION_LOCK_PATH = (HOME_PROMPT_FLOW_DIR / "encryption_key.lock").resolve()
SCRUBBED_VALUE = "******"
CHAT_HISTORY = "chat_history"

WORKSPACE_LINKED_DATASTORE_NAME = "workspaceblobstore"

LINE_NUMBER = "line_number"

AZUREML_PF_RUN_PROPERTIES_LINEAGE = "azureml.promptflow.input_run_id"

DEFAULT_ENCODING = "utf-8"


class RunTypes:
    BATCH = "batch"
    EVALUATION = "evaluation"
    PAIRWISE_EVALUATE = "pairwise_evaluate"


class AzureRunTypes:
    """Run types for run entity from index service."""

    BATCH = "azureml.promptflow.FlowRun"
    EVALUATION = "azureml.promptflow.EvaluationRun"
    PAIRWISE_EVALUATE = "azureml.promptflow.PairwiseEvaluationRun"


class RestRunTypes:
    """Run types for run entity from MT service."""

    BATCH = "FlowRun"
    EVALUATION = "EvaluationRun"
    PAIRWISE_EVALUATE = "PairwiseEvaluationRun"


# run document statuses
class RunStatus(object):
    # Ordered by transition order
    QUEUED = "Queued"
    NOT_STARTED = "NotStarted"
    PREPARING = "Preparing"
    PROVISIONING = "Provisioning"
    STARTING = "Starting"
    RUNNING = "Running"
    CANCEL_REQUESTED = "CancelRequested"
    CANCELED = "Canceled"
    FINALIZING = "Finalizing"
    COMPLETED = "Completed"
    FAILED = "Failed"
    UNAPPROVED = "Unapproved"
    NOTRESPONDING = "NotResponding"
    PAUSING = "Pausing"
    PAUSED = "Paused"

    @classmethod
    def list(cls):
        """Return the list of supported run statuses."""
        return [
            cls.QUEUED,
            cls.PREPARING,
            cls.PROVISIONING,
            cls.STARTING,
            cls.RUNNING,
            cls.CANCEL_REQUESTED,
            cls.CANCELED,
            cls.FINALIZING,
            cls.COMPLETED,
            cls.FAILED,
            cls.NOT_STARTED,
            cls.UNAPPROVED,
            cls.NOTRESPONDING,
            cls.PAUSING,
            cls.PAUSED,
        ]

    @classmethod
    def get_running_statuses(cls):
        """Return the list of running statuses."""
        return [
            cls.NOT_STARTED,
            cls.QUEUED,
            cls.PREPARING,
            cls.PROVISIONING,
            cls.STARTING,
            cls.RUNNING,
            cls.UNAPPROVED,
            cls.NOTRESPONDING,
            cls.PAUSING,
            cls.PAUSED,
        ]

    @classmethod
    def get_post_processing_statuses(cls):
        """Return the list of running statuses."""
        return [cls.CANCEL_REQUESTED, cls.FINALIZING]


class FlowRunProperties:
    FLOW_PATH = "flow_path"
    OUTPUT_PATH = "output_path"
    NODE_VARIANT = "node_variant"
    RUN = "run"


class CommonYamlFields:
    """Common yaml fields.

    Common yaml fields are used to define the common fields in yaml files. It can be one of the following values: type,
    name, $schema.
    """

    TYPE = "type"
    """Type."""
    NAME = "name"
    """Name."""
    SCHEMA = "$schema"
    """Schema."""


MAX_LIST_CLI_RESULTS = 50  # general list
MAX_RUN_LIST_RESULTS = 50  # run list
MAX_SHOW_DETAILS_RESULTS = 100  # show details


def get_run_output_path(run) -> Path:
    # store the run outputs to user's local dir
    return (Path.home() / ".promptflow/.runs" / str(run.name)).resolve()


class LocalStorageFilenames:
    SNAPSHOT_FOLDER = "snapshot"
    DAG = DAG_FILE_NAME
    INPUTS = "inputs.jsonl"
    OUTPUTS = "outputs.jsonl"
    DETAIL = "detail.json"
    METRICS = "metrics.json"
    LOG = "logs.txt"
    EXCEPTION = "error.json"


class ListViewType(str, Enum):
    ACTIVE_ONLY = "ActiveOnly"
    ARCHIVED_ONLY = "ArchivedOnly"
    ALL = "All"


def get_list_view_type(archived_only: bool, include_archived: bool) -> ListViewType:
    if archived_only and include_archived:
        raise Exception("Cannot provide both archived-only and include-archived.")
    if include_archived:
        return ListViewType.ALL
    elif archived_only:
        return ListViewType.ARCHIVED_ONLY
    else:
        return ListViewType.ACTIVE_ONLY


# run visualize constants
VISUALIZE_HTML_TEMPLATE = Path(__file__).parent / "data" / "visualize.j2"
CDN_LINK = "https://sdk-bulk-test-endpoint.azureedge.net/bulk-test-details/view/{version}/{filename}?version=1"
VISUALIZE_VERSION = "0.0.24"
JS_FILENAME = "bulkTestDetails.min.js"
CSS_FILENAME = "style.css"


class RunInfoSources(str, Enum):
    """Run sources."""

    LOCAL = "local"
    INDEX_SERVICE = "index_service"
    RUN_HISTORY = "run_history"
    MT_SERVICE = "mt_service"


class ConfigValueType(str, Enum):
    STRING = "String"
    SECRET = "Secret"


class ConnectionType(str, Enum):
    _NOT_SET = "NotSet"
    AZURE_OPEN_AI = "AzureOpenAI"
    OPEN_AI = "OpenAI"
    QDRANT = "Qdrant"
    COGNITIVE_SEARCH = "CognitiveSearch"
    SERP = "Serp"
    AZURE_CONTENT_SAFETY = "AzureContentSafety"
    FORM_RECOGNIZER = "FormRecognizer"
    WEAVIATE = "Weaviate"
    CUSTOM = "Custom"


class ConnectionFields(str, Enum):
    CONNECTION = "connection"
    DEPLOYMENT_NAME = "deployment_name"


class RunDataKeys:
    PORTAL_URL = "portal_url"
    DATA = "data"
    DATA_PORTAL_URL = "data_portal_url"
    RUN = "run"
    INPUT_RUN_PORTAL_URL = "input_run_portal_url"
    OUTPUT = "output"
    OUTPUT_PORTAL_URL = "output_portal_url"


SUPPORTED_CONNECTION_FIELDS = {
    ConnectionFields.CONNECTION.value,
    ConnectionFields.DEPLOYMENT_NAME.value,
}
