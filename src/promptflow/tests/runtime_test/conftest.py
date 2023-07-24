import os
from pathlib import Path

import pytest
from azure.ai.ml import MLClient
from pytest_mock import MockerFixture

from promptflow._constants import PROMPTFLOW_CONNECTIONS
from promptflow.runtime import PromptFlowRuntime
from promptflow.runtime.constants import PROMPTFLOW_PROJECT_PATH, PRT_CONFIG_OVERRIDE_ENV
from promptflow.runtime.serving.app import PromptflowServingApp
from promptflow.runtime.serving.app import create_app as create_serving_app

PROMOTFLOW_ROOT = Path(__file__) / "../../.."
RUNTIME_TEST_CONFIGS_ROOT = Path(PROMOTFLOW_ROOT / "tests/test_configs/runtime")
EXECUTOR_REQUESTS_ROOT = Path(PROMOTFLOW_ROOT / "tests/test_configs/executor_api_requests")
MODEL_ROOT = Path(PROMOTFLOW_ROOT / "tests/test_configs/e2e_samples")
CONNECTION_FILE = (PROMOTFLOW_ROOT / "connections.json").resolve().absolute().as_posix()


@pytest.fixture
def use_secrets_config_file(mocker: MockerFixture):
    mocker.patch.dict(os.environ, {PROMPTFLOW_CONNECTIONS: CONNECTION_FILE})


@pytest.fixture
def ml_client() -> MLClient:
    """return a machine learning client using default e2e testing workspace"""
    from ._azure_utils import get_cred

    return MLClient(
        credential=get_cred(),
        subscription_id="96aede12-2f73-41cb-b983-6d11a904839b",
        resource_group_name="promptflow",
        workspace_name="promptflow-eastus",
        # workspace_name="promptflow-canary",
        cloud="AzureCloud",
    )


@pytest.fixture
def invalid_data(ml_client):
    from ._azure_utils import get_or_create_data
    from ._utils import get_config_file

    batch_inputs_file = get_config_file(file="requests/qa_with_bing_invalid.jsonl")

    data_name = "qa_with_bing_test_invalid_data"
    return get_or_create_data(ml_client, data_name, batch_inputs_file)


@pytest.fixture
def connection_client() -> MLClient:
    """return a machine learning client for connection ARM API test"""
    from ._azure_utils import get_cred

    return MLClient(
        credential=get_cred(),
        subscription_id="96aede12-2f73-41cb-b983-6d11a904839b",
        resource_group_name="promptflow",
        workspace_name="promptflow-eastus",
        # workspace_name="promptflow-canary",
        cloud="AzureCloud",
    )


@pytest.fixture
def enterprise_serving_client(connection_client, mocker: MockerFixture) -> PromptflowServingApp:
    PromptFlowRuntime._instance = None  # Clear the _instance as we have community test
    model_path = (Path(MODEL_ROOT) / "multiple_inputs").resolve().absolute().as_posix()
    mocker.patch.dict(os.environ, {PROMPTFLOW_PROJECT_PATH: model_path})
    mocker.patch.dict(
        os.environ,
        {
            PRT_CONFIG_OVERRIDE_ENV: f"deployment.subscription_id={connection_client.subscription_id},"
            f"deployment.resource_group={connection_client.resource_group_name},"
            f"deployment.workspace_name={connection_client.workspace_name},"
            "app.port=8088",
        },
    )
    app = create_serving_app()
    app.init_executor_if_not_exist()
    app.config.update(
        {
            "TESTING": True,
        }
    )
    return app.test_client()
