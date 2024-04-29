# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------


class FlowType:
    STANDARD = "standard"
    CHAT = "chat"
    EVALUATION = "evaluate"


class FlowJobType:
    STANDARD = "azureml.promptflow.FlowRun"
    EVALUATION = "azureml.promptflow.EvaluationRun"


# Use this storage since it's the storage used by notebook
DEFAULT_STORAGE = "workspaceworkingdirectory"
PROMPTFLOW_FILE_SHARE_DIR = "promptflow"

CLOUD_RUNS_PAGE_SIZE = 25  # align with UX

SESSION_CREATION_TIMEOUT_SECONDS = 10 * 60  # 10 minutes
SESSION_CREATION_TIMEOUT_ENV_VAR = "PROMPTFLOW_SESSION_CREATION_TIMEOUT_SECONDS"
ENVIRONMENT = "environment"
PYTHON_REQUIREMENTS_TXT = "python_requirements_txt"
ADDITIONAL_INCLUDES = "additional_includes"
BASE_IMAGE = "image"


COMPUTE_SESSION_NAME = "automatic"
COMPUTE_SESSION = "compute session"
SESSION_ID_PROPERTY = "azureml.promptflow.session_id"
RUNTIME_PROPERTY = "azureml.promptflow.runtime_name"
