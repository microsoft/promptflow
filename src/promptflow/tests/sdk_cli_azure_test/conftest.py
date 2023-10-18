# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os
from pathlib import Path

import pytest
from azure.ai.ml import MLClient
from azure.ai.ml.constants._common import AZUREML_RESOURCE_PROVIDER, RESOURCE_ID_FORMAT
from azure.ai.ml.entities import Data
from azure.core.exceptions import ResourceNotFoundError
from pytest_mock import MockerFixture

from promptflow.azure import PFClient

from ._azure_utils import get_cred

FLOWS_DIR = "./tests/test_configs/flows"
DATAS_DIR = "./tests/test_configs/datas"


@pytest.fixture
def ml_client(
    default_subscription_id: str,
    default_resource_group: str,
    default_workspace: str,
) -> MLClient:
    """return a machine learning client using default e2e testing workspace"""

    return MLClient(
        credential=get_cred(),
        subscription_id=default_subscription_id,
        resource_group_name=default_resource_group,
        workspace_name=default_workspace,
        cloud="AzureCloud",
    )


@pytest.fixture()
def remote_client() -> PFClient:
    return PFClient(
        credential=get_cred(),
        subscription_id="96aede12-2f73-41cb-b983-6d11a904839b",
        resource_group_name="promptflow",
        workspace_name="promptflow-eastus",
    )


@pytest.fixture()
def remote_workspace_resource_id():
    return "azureml:" + RESOURCE_ID_FORMAT.format(
        "96aede12-2f73-41cb-b983-6d11a904839b", "promptflow", AZUREML_RESOURCE_PROVIDER, "promptflow-eastus"
    )


@pytest.fixture()
def remote_client_int() -> PFClient:
    client = MLClient(
        credential=get_cred(),
        subscription_id="96aede12-2f73-41cb-b983-6d11a904839b",
        resource_group_name="promptflow",
        workspace_name="promptflow-int",
    )
    return PFClient(ml_client=client)


@pytest.fixture()
def pf(remote_client) -> PFClient:
    return remote_client


@pytest.fixture
def remote_web_classification_data(remote_client):
    data_name, data_version = "webClassification1", "1"
    try:
        return remote_client.ml_client.data.get(name=data_name, version=data_version)
    except ResourceNotFoundError:
        return remote_client.ml_client.data.create_or_update(
            Data(name=data_name, version=data_version, path=f"{DATAS_DIR}/webClassification1.jsonl", type="uri_file")
        )


@pytest.fixture
def runtime():
    return "demo-mir"


@pytest.fixture
def runtime_int():
    return "daily-image-mir"


@pytest.fixture
def ml_client_with_acr_access(
    default_subscription_id: str,
    default_resource_group: str,
    workspace_with_acr_access: str,
) -> MLClient:
    """return a machine learning client using default e2e testing workspace"""

    return MLClient(
        credential=get_cred(),
        subscription_id=default_subscription_id,
        resource_group_name=default_resource_group,
        workspace_name=workspace_with_acr_access,
        cloud="AzureCloud",
    )


@pytest.fixture
def ml_client_int(
    default_subscription_id: str,
    default_resource_group: str,
) -> MLClient:
    """return a machine learning client using default e2e testing workspace"""

    return MLClient(
        credential=get_cred(),
        subscription_id="d128f140-94e6-4175-87a7-954b9d27db16",
        resource_group_name=default_resource_group,
        workspace_name="promptflow-int",
        cloud="AzureCloud",
    )


@pytest.fixture
def ml_client_canary(
    default_subscription_id: str,
    default_resource_group: str,
) -> MLClient:
    """return a machine learning client using default e2e testing workspace"""

    return MLClient(
        credential=get_cred(),
        subscription_id=default_subscription_id,
        resource_group_name=default_resource_group,
        workspace_name="promptflow-canary-dev",
        cloud="AzureCloud",
    )


PROMPTFLOW_ROOT = Path(__file__) / "../../.."
MODEL_ROOT = Path(PROMPTFLOW_ROOT / "tests/test_configs/flows")


@pytest.fixture
def flow_serving_client_remote_connection(mocker: MockerFixture, remote_workspace_resource_id):
    from promptflow._sdk._serving.app import create_app as create_serving_app

    model_path = (Path(MODEL_ROOT) / "basic-with-connection").resolve().absolute().as_posix()
    mocker.patch.dict(os.environ, {"PROMPTFLOW_PROJECT_PATH": model_path})
    mocker.patch.dict(os.environ, {"USER_AGENT": "test-user-agent"})
    app = create_serving_app(
        connection_provider=remote_workspace_resource_id,
        environment_variables={"API_TYPE": "${azure_open_ai_connection.api_type}"},
    )
    app.config.update(
        {
            "TESTING": True,
        }
    )
    return app.test_client()
