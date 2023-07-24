import sys
from pathlib import Path

import pytest
import yaml
from azure.ai.ml import MLClient
from azure.identity import AzureCliCredential

from promptflow.storage.azureml_run_storage import AzureMLRunStorage
from promptflow.utils.utils import get_mlflow_tracking_uri

from .endpoint_client import PromptflowEndpointClient

PROMOTFLOW_ROOT = Path(__file__) / "../../.."
root_dir = PROMOTFLOW_ROOT
test_root_dir = PROMOTFLOW_ROOT / "tests"


def inject_path(path: Path):
    path_str = str(path.resolve().absolute())
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


inject_path(root_dir)
inject_path(test_root_dir)


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
def endpoint_name(deployment_model_config):
    deployment = deployment_model_config["deployment"]
    endpoint_name = deployment.get("endpoint_name", None)
    if not endpoint_name:
        raise ValueError("Missing endpoint_name in model file config, please add it and test again.")
    return endpoint_name


@pytest.fixture(scope="session")
def deployment_name(deployment_model_config):
    deployment = deployment_model_config["deployment"]
    deployment_name = deployment.get("deployment_name", None)
    if not deployment_name:
        raise ValueError("Missing deployment_name in model file config, please add it and test again.")
    return deployment_name


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
def prt_execute_config(ml_client, endpoint_name, deployment_name):
    try:
        endpoint = ml_client.online_endpoints.get(endpoint_name)
        endpoint_url = endpoint.scoring_uri.replace("/score", "")
        endpoint_key = ml_client.online_endpoints.get_keys(endpoint_name).primary_key
        if deployment_name not in endpoint.traffic:
            raise ValueError(f"Deployment {deployment_name} not found in endpoint {endpoint_name}")
    except:  # noqa: E722
        raise ValueError(f"Endpoint {endpoint_name} not found in workspace {ml_client.workspace_name}")

    return {
        "connection_file_path": (PROMOTFLOW_ROOT / "connections.json").resolve().absolute().as_posix(),
        "endpoint_url": endpoint_url,
        "endpoint_key": endpoint_key,
        "deployment_name": deployment_name,
    }


@pytest.fixture(scope="session")
def endpoint_client(prt_execute_config, ml_client):
    return PromptflowEndpointClient(prt_execute_config, ml_client)


@pytest.fixture(scope="session")
def azure_run_storage(deployment_model_config, ml_client):
    deployment = deployment_model_config["deployment"]
    mlflow_tracking_uri = get_mlflow_tracking_uri(
        subscription_id=deployment["subscription_id"],
        resource_group_name=deployment["resource_group"],
        workspace_name=deployment["workspace_name"],
        mt_endpoint=deployment["mt_service_endpoint"],
    )

    return AzureMLRunStorage(
        deployment_model_config["storage"]["storage_account"],
        mlflow_tracking_uri=mlflow_tracking_uri,
        credential=AzureCliCredential(),
        ml_client=ml_client,
    )
