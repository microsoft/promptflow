import os

from promptflow.core import RunTracker
from promptflow.storage.azureml_run_storage import AzureMLRunStorage

from ..utils import logger


def init_run_tracker() -> "RunTracker":
    """Initialize RunTracker in AML Compute, it's for PRS usage only.
    Returns:
        RunTracker: RunTracker instance.
    """
    from azure.ai.ml import MLClient
    from azure.identity import ManagedIdentityCredential
    from azureml.core import Run

    default_identity_id = os.environ.get("DEFAULT_IDENTITY_CLIENT_ID", None)
    cred = ManagedIdentityCredential(client_id=default_identity_id)

    run = Run.get_context()
    subscription_id = run.experiment.workspace.subscription_id
    resource_group = run.experiment.workspace.resource_group
    workspace = run.experiment.workspace.name
    logger.info(f"Subscription_id: {subscription_id}, resource_group: {resource_group}, workspace: {workspace}")

    ml_client = MLClient(cred, subscription_id, resource_group, workspace)
    ws = ml_client.workspaces.get()
    storage_account = ws.storage_account.split("/")[-1]
    logger.info(f"Storage_account: {storage_account}")

    run_storage = AzureMLRunStorage(
        storage_account, mlflow_tracking_uri=os.environ["MLFLOW_TRACKING_URI"], credential=cred, ml_client=ml_client
    )

    return RunTracker(run_storage)
