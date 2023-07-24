from pathlib import Path

import pytest
import yaml
from azure.ai.ml import MLClient
from azure.identity import AzureCliCredential

from promptflow.storage.azureml_run_storage import AzureMLRunStorage

from .mt_client import PromptflowClient


@pytest.fixture(scope="session")
def deployment_model_config(request):
    model_name = request.config.getoption("--model-name", default="promptflow-int-latest.yaml")
    print("model_name: ", model_name)
    model_file = Path(__file__).parent / "../../../../deploy/model/" / model_name
    model_file = model_file.resolve().absolute()
    if not model_file.exists():
        raise FileNotFoundError(f"Missing {str(model_file)!r}, please update the file path if it's moved elsewhere.")
    with open(model_file, "r") as f:
        result = yaml.safe_load(f)
    return result


@pytest.fixture(scope="session")
def ml_client(deployment_model_config) -> MLClient:
    deployment = deployment_model_config["deployment"]
    return MLClient(
        credential=AzureCliCredential(),
        subscription_id=deployment["subscription_id"],
        resource_group_name=deployment["resource_group"],
        workspace_name=deployment["workspace_name"],
    )


@pytest.fixture(scope="session")
def promptflow_client(deployment_model_config, ml_client):
    deployment = deployment_model_config["deployment"]
    return PromptflowClient(deployment, ml_client)


@pytest.fixture(scope="session")
def azure_run_storage(deployment_model_config, ml_client):
    mlflow_tracking_uri = ml_client.workspaces.get().mlflow_tracking_uri
    return AzureMLRunStorage(
        deployment_model_config["storage"]["storage_account"],
        mlflow_tracking_uri=mlflow_tracking_uri,
        credential=AzureCliCredential(),
        ml_client=ml_client,
    )
