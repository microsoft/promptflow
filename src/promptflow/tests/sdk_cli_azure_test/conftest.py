# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import logging

import pytest
from azure.ai.ml import MLClient
from azure.ai.ml.entities import Data
from azure.core.exceptions import ResourceNotFoundError
from pytest_mock import MockFixture

from promptflow.azure import PFClient

from ._azure_utils import get_cred
from .recording_utilities import PFAzureIntegrationTestRecording, get_pf_client_for_playback, is_live

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


@pytest.fixture
def remote_client() -> PFClient:
    if not is_live():
        return get_pf_client_for_playback()

    return PFClient(
        credential=get_cred(),
        subscription_id="96aede12-2f73-41cb-b983-6d11a904839b",
        resource_group_name="promptflow",
        workspace_name="promptflow-eastus",
    )


@pytest.fixture
def remote_client_int() -> PFClient:
    if not is_live():
        return get_pf_client_for_playback()

    return PFClient(
        credential=get_cred(),
        subscription_id="96aede12-2f73-41cb-b983-6d11a904839b",
        resource_group_name="promptflow",
        workspace_name="promptflow-int",
    )


@pytest.fixture
def pf(remote_client: PFClient) -> PFClient:
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
def runtime() -> str:
    return "demo-mir"


@pytest.fixture
def runtime_int() -> str:
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


@pytest.fixture(scope="function", autouse=True)
def vcr_recording(request: pytest.FixtureRequest) -> None:
    recording = PFAzureIntegrationTestRecording(
        test_class=request.cls,
        test_func_name=request.node.name,
    )
    recording.enter_vcr()
    request.addfinalizer(recording.exit_vcr)
    yield


@pytest.fixture(autouse=True)
def mock_appinsights_log_handler(mocker: MockFixture) -> None:
    dummy_logger = logging.getLogger("dummy")
    mocker.patch("promptflow._telemetry.telemetry.get_telemetry_logger", return_value=dummy_logger)
