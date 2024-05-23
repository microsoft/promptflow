# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os
from collections import namedtuple
from enum import Enum
from pathlib import Path

from promptflow._constants import (
    AZURE_WORKSPACE_REGEX_FORMAT,
    CONNECTION_SCRUBBED_VALUE,
    CONNECTION_SCRUBBED_VALUE_NO_CHANGE,
    PROMPT_FLOW_DIR_NAME,
    ConnectionType,
    CustomStrongTypeConnectionConfigs,
)
from promptflow.constants import ConnectionAuthMode

LOGGER_NAME = "promptflow"

PROMPT_FLOW_HOME_DIR_ENV_VAR = "PF_HOME_DIRECTORY"
# Please avoid using PROMPT_FLOW_DIR_NAME directly for home directory, "Path.home() / PROMPT_FLOW_DIR_NAME" e.g.
# Use HOME_PROMPT_FLOW_DIR instead
PROMPT_FLOW_DIR_NAME = PROMPT_FLOW_DIR_NAME
DEFAULT_SERVE_ENGINE = "flask"


def _prepare_home_dir() -> Path:
    """Prepare prompt flow home directory.

    User can configure it by setting environment variable: `PF_HOME_DIRECTORY`;
    if not configured, or configured value is not valid, use default value: "~/.promptflow/".
    """
    from promptflow._utils.logger_utils import get_cli_sdk_logger

    logger = get_cli_sdk_logger()

    if PROMPT_FLOW_HOME_DIR_ENV_VAR in os.environ:
        logger.debug(
            f"environment variable {PROMPT_FLOW_HOME_DIR_ENV_VAR!r} is set, honor it preparing home directory."
        )
        try:
            pf_home_dir = Path(os.getenv(PROMPT_FLOW_HOME_DIR_ENV_VAR)).resolve()
            pf_home_dir.mkdir(parents=True, exist_ok=True)
            return pf_home_dir
        except Exception as e:  # pylint: disable=broad-except
            _warning_message = (
                "Invalid configuration for prompt flow home directory: "
                f"{os.getenv(PROMPT_FLOW_HOME_DIR_ENV_VAR)!r}: {str(e)!r}.\n"
                'Fall back to use default value: "~/.promptflow/".'
            )
            logger.warning(_warning_message)

    try:
        logger.debug("preparing home directory with default value.")
        pf_home_dir = (Path.home() / PROMPT_FLOW_DIR_NAME).resolve()
        pf_home_dir.mkdir(parents=True, exist_ok=True)
        return pf_home_dir
    except Exception as e:  # pylint: disable=broad-except
        _error_message = (
            f"Cannot create prompt flow home directory: {str(e)!r}.\n"
            "Please check if you have proper permission to operate the directory "
            f"{HOME_PROMPT_FLOW_DIR.as_posix()!r}; or configure it via "
            f"environment variable {PROMPT_FLOW_HOME_DIR_ENV_VAR!r}.\n"
        )
        logger.error(_error_message)
        raise Exception(_error_message)


HOME_PROMPT_FLOW_DIR = _prepare_home_dir()

DEFAULT_REQUIREMENTS_FILE_NAME = "requirements.txt"
NODE_VARIANTS = "node_variants"
VARIANTS = "variants"
NODES = "nodes"
NODE = "node"
INPUTS = "inputs"
USE_VARIANTS = "use_variants"
DEFAULT_VAR_ID = "default_variant_id"
FLOW_TOOLS_JSON = "flow.tools.json"
FLOW_META_JSON = "flow.json"
SERVE_SAMPLE_JSON_PATH = "sample.json"
FLOW_TOOLS_JSON_GEN_TIMEOUT = 60
FLOW_META_JSON_GEN_TIMEOUT = 60
PROMPT_FLOW_RUNS_DIR_NAME = ".runs"
PROMPT_FLOW_EXP_DIR_NAME = ".exps"
SERVICE_CONFIG_FILE = "pf.yaml"
PF_SERVICE_PORT_DIT_NAME = "pfs"
PF_SERVICE_PORT_FILE = "pfs.port"
PF_SERVICE_LOG_FILE = "pfs.log"
PF_SERVICE_HOST = "127.0.0.1"
PF_SERVICE_DEFAULT_PORT = 23333
PF_SERVICE_HOUR_TIMEOUT = 1
PF_SERVICE_MONITOR_SECOND = 60
PF_SERVICE_WORKER_NUM = 16
PF_TRACE_CONTEXT = "PF_TRACE_CONTEXT"
PF_TRACE_CONTEXT_ATTR = "attributes"
PF_SERVICE_DEBUG = "PF_SERVICE_DEBUG"
PF_SYSTEM_METRICS_PREFIX = "__pf__"

LOCAL_MGMT_DB_PATH = (HOME_PROMPT_FLOW_DIR / "pf.sqlite").resolve()
LOCAL_MGMT_DB_SESSION_ACQUIRE_LOCK_PATH = (HOME_PROMPT_FLOW_DIR / "pf.sqlite.lock").resolve()
SCHEMA_INFO_TABLENAME = "schema_info"
RUN_INFO_TABLENAME = "run_info"
RUN_INFO_CREATED_ON_INDEX_NAME = "idx_run_info_created_on"
CONNECTION_TABLE_NAME = "connection"
EXPERIMENT_TABLE_NAME = "experiment"
ORCHESTRATOR_TABLE_NAME = "orchestrator"
EXP_NODE_RUN_TABLE_NAME = "exp_node_run"
EXPERIMENT_CREATED_ON_INDEX_NAME = "idx_experiment_created_on"
BASE_PATH_CONTEXT_KEY = "base_path"
SCHEMA_KEYS_CONTEXT_CONFIG_KEY = "schema_configs_keys"
SCHEMA_KEYS_CONTEXT_SECRET_KEY = "schema_secrets_keys"
PARAMS_OVERRIDE_KEY = "params_override"
FILE_PREFIX = "file:"
KEYRING_SYSTEM = "promptflow"
KEYRING_ENCRYPTION_KEY_NAME = "encryption_key"
KEYRING_ENCRYPTION_LOCK_PATH = (HOME_PROMPT_FLOW_DIR / "encryption_key.lock").resolve()
REFRESH_CONNECTIONS_DIR_LOCK_PATH = (HOME_PROMPT_FLOW_DIR / "refresh_connections_dir.lock").resolve()
# Note: Use this only for show. Reading input should regard all '*' string as scrubbed, no matter the length.
SCRUBBED_VALUE = CONNECTION_SCRUBBED_VALUE
SCRUBBED_VALUE_NO_CHANGE = CONNECTION_SCRUBBED_VALUE_NO_CHANGE
SCRUBBED_VALUE_USER_INPUT = "<user-input>"
WORKSPACE_LINKED_DATASTORE_NAME = "workspaceblobstore"
LINE_NUMBER = "line_number"
AZUREML_PF_RUN_PROPERTIES_LINEAGE = "azureml.promptflow.input_run_id"
AZURE_WORKSPACE_REGEX_FORMAT = AZURE_WORKSPACE_REGEX_FORMAT
DEFAULT_ENCODING = "utf-8"
LOCAL_STORAGE_BATCH_SIZE = 1
LOCAL_SERVICE_PORT = 5000
BULK_RUN_ERRORS = "BulkRunErrors"
RUN_MACRO = "${run}"
VARIANT_ID_MACRO = "${variant_id}"
TIMESTAMP_MACRO = "${timestamp}"
DEFAULT_VARIANT = "variant_0"
# run visualize constants
VIS_HTML_TMPL = Path(__file__).parent / "data" / "visualize.j2"
VIS_PORTAL_URL_TMPL = (
    "https://ml.azure.com/prompts/flow/bulkrun/runs/outputs"
    "?wsid=/subscriptions/{subscription_id}/resourceGroups/{resource_group_name}"
    "/providers/Microsoft.MachineLearningServices/workspaces/{workspace_name}&runId={names}"
)
REMOTE_URI_PREFIX = "azureml:"
REGISTRY_URI_PREFIX = "azureml://registries/"
FLOW_RESOURCE_ID_PREFIX = "azureml://locations/"
FLOW_DIRECTORY_MACRO_IN_CONFIG = "${flow_directory}"

# trace
TRACE_DEFAULT_SESSION_ID = "default"
TRACE_DEFAULT_COLLECTION = "default"
TRACE_MGMT_DB_PATH = (HOME_PROMPT_FLOW_DIR / "trace.sqlite").resolve()
TRACE_MGMT_DB_SESSION_ACQUIRE_LOCK_PATH = (HOME_PROMPT_FLOW_DIR / "trace.sqlite.lock").resolve()
EVENT_TABLENAME = "events"
SPAN_TABLENAME = "spans"
LINE_RUN_TABLENAME = "line_runs"
PFS_MODEL_DATETIME_FORMAT = "iso8601"
SPAN_EVENTS_NAME_PF_INPUTS = "promptflow.function.inputs"
SPAN_EVENTS_NAME_PF_OUTPUT = "promptflow.function.output"
SPAN_EVENTS_ATTRIBUTE_PAYLOAD = "payload"

UX_INPUTS_JSON = "ux.inputs.json"
UX_INPUTS_INIT_KEY = "init"
AzureMLWorkspaceTriad = namedtuple("AzureMLWorkspace", ["subscription_id", "resource_group_name", "workspace_name"])

# chat group
STOP_SIGNAL = "[STOP]"
CHAT_GROUP_REFERENCE_NAME = "parent"
CONVERSATION_HISTORY = "conversation_history"


class RunTypes:
    BATCH = "batch"
    EVALUATION = "evaluation"
    PAIRWISE_EVALUATE = "pairwise_evaluate"
    COMMAND = "command"
    CHAT_GROUP = "chat_group"


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

    @classmethod
    def get_terminated_statuses(cls):
        """Return the list of terminated statuses."""
        return [cls.COMPLETED, cls.FAILED, cls.CANCELED]


class FlowRunProperties:
    FLOW_PATH = "flow_path"
    OUTPUT_PATH = "output_path"
    NODE_VARIANT = "node_variant"
    RUN = "run"
    SYSTEM_METRICS = "system_metrics"
    # Experiment command node fields only
    COMMAND = "command"
    OUTPUTS = "outputs"
    RESUME_FROM = "resume_from"
    COLUMN_MAPPING = "column_mapping"
    INIT_KWARGS = "init_kwargs"


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


class CLIListOutputFormat:
    JSON = "json"
    TABLE = "table"


class LocalStorageFilenames:
    SNAPSHOT_FOLDER = "snapshot"
    FLOW_TOOLS_JSON = FLOW_TOOLS_JSON
    INPUTS = "inputs.jsonl"
    OUTPUTS = "outputs.jsonl"
    DETAIL = "detail.json"
    METRICS = "metrics.json"
    LOG = "logs.txt"
    FLOW_LOGS_FOLDER = "flow_logs"
    EXCEPTION = "error.json"
    META = "meta.json"


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


class RunInfoSources(str, Enum):
    """Run sources."""

    LOCAL = "local"
    INDEX_SERVICE = "index_service"
    RUN_HISTORY = "run_history"
    MT_SERVICE = "mt_service"
    EXISTING_RUN = "existing_run"


class ConfigValueType(str, Enum):
    STRING = "String"
    SECRET = "Secret"


ALL_CONNECTION_TYPES = set(
    map(lambda x: f"{x.value}Connection", filter(lambda x: x != ConnectionType._NOT_SET, ConnectionType))
)


class ConnectionFields(str, Enum):
    CONNECTION = "connection"
    DEPLOYMENT_NAME = "deployment_name"
    MODEL = "model"


SUPPORTED_CONNECTION_FIELDS = {
    ConnectionFields.CONNECTION.value,
    ConnectionFields.DEPLOYMENT_NAME.value,
    ConnectionFields.MODEL.value,
}


class RunDataKeys:
    PORTAL_URL = "portal_url"
    DATA = "data"
    RUN = "run"
    OUTPUT = "output"


class RunHistoryKeys:
    RunMetaData = "runMetadata"
    HIDDEN = "hidden"


class FlowType:
    STANDARD = "standard"
    EVALUATION = "evaluation"
    CHAT = "chat"

    @staticmethod
    def get_all_values():
        values = [value for key, value in vars(FlowType).items() if isinstance(value, str) and key.isupper()]
        return values


CLIENT_FLOW_TYPE_2_SERVICE_FLOW_TYPE = {
    FlowType.STANDARD: "default",
    FlowType.EVALUATION: "evaluation",
    FlowType.CHAT: "chat",
}

SERVICE_FLOW_TYPE_2_CLIENT_FLOW_TYPE = {value: key for key, value in CLIENT_FLOW_TYPE_2_SERVICE_FLOW_TYPE.items()}


class AzureFlowSource:
    LOCAL = "local"
    PF_SERVICE = "pf_service"
    INDEX = "index"


class DownloadedRun:
    SNAPSHOT_FOLDER = LocalStorageFilenames.SNAPSHOT_FOLDER
    METRICS_FILE_NAME = LocalStorageFilenames.METRICS
    LOGS_FILE_NAME = LocalStorageFilenames.LOG
    RUN_METADATA_FILE_NAME = "run_metadata.json"


class ExperimentNodeType(object):
    FLOW = "flow"
    CHAT_GROUP = "chat_group"
    COMMAND = "command"


EXP_NODE_TYPE_2_RUN_TYPE = {
    ExperimentNodeType.FLOW: RunTypes.BATCH,
    ExperimentNodeType.CHAT_GROUP: RunTypes.CHAT_GROUP,
    ExperimentNodeType.COMMAND: RunTypes.COMMAND,
}


class ExperimentStatus(object):
    NOT_STARTED = "NotStarted"
    QUEUING = "Queuing"
    IN_PROGRESS = "InProgress"
    TERMINATED = "Terminated"


class ExperimentNodeRunStatus(object):
    NOT_STARTED = "NotStarted"
    QUEUING = "Queuing"
    IN_PROGRESS = "InProgress"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELED = "Canceled"


class ContextAttributeKey:
    EXPERIMENT = "experiment"
    # Note: referenced id not used for lineage, only for evaluation
    REFERENCED_LINE_RUN_ID = "referenced.line_run_id"
    REFERENCED_BATCH_RUN_ID = "referenced.batch_run_id"


class EnvironmentVariables:
    """The environment variables."""

    PF_USE_AZURE_CLI_CREDENTIAL = "PF_USE_AZURE_CLI_CREDENTIAL"


class CumulativeTokenCountFieldName:
    COMPLETION = "completion"
    PROMPT = "prompt"
    TOTAL = "total"


class LineRunFieldName:
    LINE_RUN_ID = "line_run_id"
    TRACE_ID = "trace_id"
    ROOT_SPAN_ID = "root_span_id"
    INPUTS = "inputs"
    OUTPUTS = "outputs"
    START_TIME = "start_time"
    END_TIME = "end_time"
    STATUS = "status"
    LATENCY = "latency"
    NAME = "name"
    KIND = "kind"
    CUMULATIVE_TOKEN_COUNT = "cumulative_token_count"
    EVALUATIONS = "evaluations"


class Local2Cloud:
    BLOB_ROOT_PROMPTFLOW = "promptflow"
    BLOB_ROOT_RUNS = "runs"
    BLOB_ARTIFACTS = "PromptFlowArtifacts"
    BLOB_EXPERIMENT_RUN = "ExperimentRun"
    ASSET_NAME_DEBUG_INFO = "debug_info"
    ASSET_NAME_FLOW_OUTPUTS = "flow_outputs"
    EXECUTION_LOG = "logs/azureml/executionlogs.txt"
    # instance_results.jsonl contains the inputs and outputs of all lines
    FLOW_INSTANCE_RESULTS_FILE_NAME = "instance_results.jsonl"


class Local2CloudProperties:
    """Run properties that server needs when uploading local run to cloud."""

    PREFIX = "azureml.promptflow"
    EVAL_ARTIFACTS = "_azureml.evaluate_artifacts"


class Local2CloudUserProperties:
    """Run properties that user can specify when uploading local run to cloud."""

    RUN_TYPE = "runType"

    @staticmethod
    def get_all_values():
        values = [
            value for key, value in vars(Local2CloudUserProperties).items() if isinstance(value, str) and key.isupper()
        ]
        return values


class CloudDatastore:
    DEFAULT = "workspaceblobstore"
    ARTIFACT = "workspaceartifactstore"


class CreatedByFieldName:
    OBJECT_ID = "object_id"
    TENANT_ID = "tenant_id"
    NAME = "name"


class ChatGroupSpeakOrder(str, Enum):
    SEQUENTIAL = "sequential"
    LLM = "llm"


TRACE_LIST_DEFAULT_LIMIT = 1000
TRACE_COLLECTION_LIST_DEFAULT_LIMIT = 100
PF_TRACING_SKIP_EXPORTER_SETUP_ENVIRON = "PF_TRACING_SKIP_EXPORTER_SETUP"


class IdentityKeys(str, Enum):
    """Enum for identity keys."""

    MANAGED = "managed"
    USER_IDENTITY = "user_identity"
    RESOURCE_ID = "resource_id"
    CLIENT_ID = "client_id"


class OSType:
    WINDOWS = "Windows"
    LINUX = "Linux"


class SignatureValueType(str, Enum):
    STRING = "string"
    NUMBER = "number"
    INT = "integer"
    OBJECT = "object"
    ARRAY = "array"
    BOOL = "boolean"
    # null will be controlled by required field
    # NULL = "null"


class RunMode:
    EAGER = "Eager"


# Note: Keep these for backward compatibility
CustomStrongTypeConnectionConfigs = CustomStrongTypeConnectionConfigs
ConnectionType = ConnectionType
ConnectionAuthMode = ConnectionAuthMode
