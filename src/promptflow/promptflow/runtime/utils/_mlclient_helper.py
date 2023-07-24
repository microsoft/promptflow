import os
import re

from azure.ai.ml import MLClient
from ._token_utils import get_default_credential


MLFLOW_TRACKING_URI_ENV = "MLFLOW_TRACKING_URI"


def get_mlclient_from_env(cred=None) -> MLClient:
    """
    Try to get mlclient from environment variable.

    Args:
        uri: MLFLOW_TRACKING_URI

    Returns:
        azure.ai.ml.MLClient
    """
    uri = os.environ.get(MLFLOW_TRACKING_URI_ENV, None)
    if uri is None or not uri.startswith("azureml:"):
        return None

    if cred is None:
        cred = get_default_credential()
    client = None
    pattern = (
        r"/subscriptions/(?P<subscription_id>[^/]+)/resourceGroups/(?P<resource_group>[^/]+)/"
        + r"providers/Microsoft.MachineLearningServices/workspaces/(?P<workspace_name>[^/]+)"
    )
    match = re.search(pattern, uri)
    if match:
        subscription_id = match.group("subscription_id")
        resource_group = match.group("resource_group")
        workspace_name = match.group("workspace_name")

        client = MLClient(
            credential=cred,
            subscription_id=subscription_id,
            resource_group_name=resource_group,
            workspace_name=workspace_name,
        )
    return client
