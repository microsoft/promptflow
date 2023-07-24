# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from enum import Enum
from pathlib import Path


class Color:
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    DARKCYAN = "\033[36m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"


DAG_FILE_NAME = "flow.dag.yaml"
NODE_VARIANTS = "node_variants"
VARIANTS = "variants"
NODES = "nodes"
NODE = "node"
USE_VARIANTS = "use_variants"
DEFAULT_VAR_ID = "default_variant_id"

HOME_PROMPT_FLOW_DIR = (Path.home() / ".promptflow").resolve()
if not HOME_PROMPT_FLOW_DIR.is_dir():
    HOME_PROMPT_FLOW_DIR.mkdir(exist_ok=True)

LOCAL_MGMT_DB_PATH = (HOME_PROMPT_FLOW_DIR / "pf.sqlite").resolve()
LOCAL_MGMT_DB_SESSION_ACQUIRE_LOCK_PATH = (HOME_PROMPT_FLOW_DIR / "pf.sqlite.lock").resolve()
RUN_INFO_TABLENAME = "run_info"
CONNECTION_TABLE_NAME = "connection"
BASE_PATH_CONTEXT_KEY = "base_path"
PARAMS_OVERRIDE_KEY = "params_override"
FILE_PREFIX = "file:"
KEYRING_SYSTEM = "promptflow"
KEYRING_ENCRYPTION_KEY_NAME = "encryption_key"
KEYRING_ENCRYPTION_LOCK_PATH = (HOME_PROMPT_FLOW_DIR / "encryption_key.lock").resolve()
PORTAL_URL_KEY = "portal_url"
SCRUBBED_VALUE = "******"


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
    return (Path(run.flow) / ".runs" / str(run.name)).resolve()


class LocalStorageFilenames:
    SNAPSHOT_FOLDER = "snapshot"
    DAG = DAG_FILE_NAME
    INPUTS = "inputs.jsonl"
    OUTPUTS = "outputs.jsonl"
    DETAIL = "detail.json"
    METRICS = "metrics.json"
    LOG = "logs.txt"


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


class VisualizeDetailConstants:
    TEMPLATE_FOLDER_PATH = Path(__file__).parent / "data"
    JINJA2_TEMPLATE = TEMPLATE_FOLDER_PATH / "detail_template.j2"
    HTML_TEMPLATE = TEMPLATE_FOLDER_PATH / "visualize_detail_template.html"
    DATA_PLACEHOLDER = "##DATA_PLACEHOLDER##"
    CDN_PLACEHOLDER = "##CDN_PLACEHOLDER##"
    # provided by UX
    CDN_LINK = "https://sdk-bulk-test-endpoint.azureedge.net/bulk-test-details/view/0.0.8/bulkTestDetails.js"


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
    CUSTOM = "Custom"
