# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import logging
from dataclasses import dataclass

import pytest
from azure.ai.ml import MLClient
from azure.ai.ml.entities import Data, Workspace
from azure.core.exceptions import ResourceNotFoundError
from pytest_mock import MockFixture

from promptflow.azure import PFClient

from ._azure_utils import get_cred
from ._fake_credentials import FakeTokenCredential
from ._recording_utils import SanitizedValues, is_live

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


@dataclass
class MockDatastore:
    """Mock Datastore class for `DatastoreOperations.get_default().name`."""

    name: str


@pytest.fixture(scope="class")
def remote_client(request: pytest.FixtureRequest) -> PFClient:
    if is_live():
        remote_client = PFClient(
            credential=get_cred(),
            subscription_id="96aede12-2f73-41cb-b983-6d11a904839b",
            resource_group_name="promptflow",
            workspace_name="promptflow-eastus",
        )
    else:
        ml_client = MLClient(
            credential=FakeTokenCredential(),
            subscription_id=SanitizedValues.SUBSCRIPTION_ID,
            resource_group_name=SanitizedValues.RESOURCE_GROUP_NAME,
            workspace_name=SanitizedValues.WORKSPACE_NAME,
        )
        ml_client.workspaces.get = lambda *args, **kwargs: Workspace(
            name=SanitizedValues.WORKSPACE_NAME,
            resource_group=SanitizedValues.RESOURCE_GROUP_NAME,
            discovery_url="https://eastus2euap.api.azureml.ms/discovery",
        )
        ml_client.datastores.get_default = lambda *args, **kwargs: MockDatastore(name="workspaceblobstore")
        remote_client = PFClient(ml_client=ml_client)

    request.cls.remote_client = remote_client
    return request.cls.remote_client


@pytest.fixture()
def remote_client_int() -> PFClient:
    client = MLClient(
        credential=get_cred(),
        subscription_id="96aede12-2f73-41cb-b983-6d11a904839b",
        resource_group_name="promptflow",
        workspace_name="promptflow-int",
    )
    return PFClient(ml_client=client)


@pytest.fixture(scope="class")
def pf(request: pytest.FixtureRequest, remote_client: PFClient) -> PFClient:
    request.cls.pf = remote_client
    return request.cls.pf


@pytest.fixture
def remote_web_classification_data(remote_client):
    data_name, data_version = "webClassification1", "1"
    try:
        return remote_client.ml_client.data.get(name=data_name, version=data_version)
    except ResourceNotFoundError:
        return remote_client.ml_client.data.create_or_update(
            Data(name=data_name, version=data_version, path=f"{DATAS_DIR}/webClassification1.jsonl", type="uri_file")
        )


@pytest.fixture(scope="class")
def runtime(request: pytest.FixtureRequest) -> None:
    request.cls.runtime = "demo-mir"


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


@pytest.fixture(autouse=True)
def mock_appinsights_log_handler(mocker: MockFixture) -> None:
    dummy_logger = logging.getLogger("dummy")
    mocker.patch("promptflow._telemetry.telemetry.get_telemetry_logger", return_value=dummy_logger)
