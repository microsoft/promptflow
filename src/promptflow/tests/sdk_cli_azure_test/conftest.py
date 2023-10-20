# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable
from unittest.mock import patch

import jwt
import pytest
from azure.ai.ml import MLClient
from azure.ai.ml.constants._common import AZUREML_RESOURCE_PROVIDER, RESOURCE_ID_FORMAT
from azure.ai.ml.entities import Data
from azure.core.exceptions import ResourceNotFoundError
from pytest_mock import MockerFixture

from promptflow._telemetry.telemetry import TELEMETRY_ENABLED
from promptflow._utils.utils import environment_variable_overwrite
from promptflow.azure import PFClient

from ._azure_utils import get_cred
from .recording_utilities import (
    PFAzureIntegrationTestRecording,
    get_pf_client_for_playback,
    is_live,
    is_live_and_not_recording,
)

FLOWS_DIR = "./tests/test_configs/flows"
DATAS_DIR = "./tests/test_configs/datas"


@pytest.fixture
def tenant_id() -> str:
    if not is_live():
        return ""
    credential = get_cred()
    access_token = credential.get_token("https://management.azure.com/.default")
    decoded_token = jwt.decode(access_token.token, options={"verify_signature": False})
    return decoded_token["tid"]


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
        yield get_pf_client_for_playback()
    else:
        # enable telemetry for CI
        with environment_variable_overwrite(TELEMETRY_ENABLED, "true"):
            yield PFClient(
                credential=get_cred(),
                subscription_id="96aede12-2f73-41cb-b983-6d11a904839b",
                resource_group_name="promptflow",
                workspace_name="promptflow-eastus",
            )


@pytest.fixture()
def remote_workspace_resource_id() -> str:
    return "azureml:" + RESOURCE_ID_FORMAT.format(
        "96aede12-2f73-41cb-b983-6d11a904839b", "promptflow", AZUREML_RESOURCE_PROVIDER, "promptflow-eastus"
    )


@pytest.fixture
def remote_client_int() -> PFClient:
    if not is_live():
        yield get_pf_client_for_playback()
    else:
        # enable telemetry for non-playback CI
        with environment_variable_overwrite(TELEMETRY_ENABLED, "true"):
            client = MLClient(
                credential=get_cred(),
                subscription_id="96aede12-2f73-41cb-b983-6d11a904839b",
                resource_group_name="promptflow",
                workspace_name="promptflow-int",
            )
            yield PFClient(ml_client=client)


@pytest.fixture()
def pf(remote_client: PFClient) -> PFClient:
    yield remote_client


@pytest.fixture
def remote_web_classification_data(remote_client: PFClient) -> Data:
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


PROMPTFLOW_ROOT = Path(__file__) / "../../.."
MODEL_ROOT = Path(PROMPTFLOW_ROOT / "tests/test_configs/flows")


@pytest.fixture
def flow_serving_client_remote_connection(mocker: MockerFixture, remote_workspace_resource_id):
    from promptflow._sdk._serving.app import create_app as create_serving_app

    model_path = (Path(MODEL_ROOT) / "basic-with-connection").resolve().absolute().as_posix()
    mocker.patch.dict(os.environ, {"PROMPTFLOW_PROJECT_PATH": model_path})
    mocker.patch.dict(os.environ, {"USER_AGENT": "test-user-agent"})
    app = create_serving_app(
        config={"connection.provider": remote_workspace_resource_id},
        environment_variables={"API_TYPE": "${azure_open_ai_connection.api_type}"},
    )
    app.config.update(
        {
            "TESTING": True,
        }
    )
    return app.test_client()


@pytest.fixture(scope="function")
def vcr_recording(request: pytest.FixtureRequest, tenant_id: str) -> PFAzureIntegrationTestRecording:
    recording = PFAzureIntegrationTestRecording.from_test_case(
        test_class=request.cls,
        test_func_name=request.node.name,
        tenant_id=tenant_id,
    )
    recording.enter_vcr()
    request.addfinalizer(recording.exit_vcr)
    yield recording


@pytest.fixture
def randstr(vcr_recording: PFAzureIntegrationTestRecording) -> Callable[[str], str]:
    """Return a random UUID."""

    def generate_random_string(variable_name: str) -> str:
        random_string = str(uuid.uuid4())
        return vcr_recording.get_or_record_variable(variable_name, random_string)

    return generate_random_string


# we expect this fixture only work when running live test without recording
# when recording, we don't want to record any application insights secrets
# when replaying, we also don't need this
@pytest.fixture(autouse=not is_live_and_not_recording())
def mock_appinsights_log_handler(mocker: MockerFixture) -> None:
    dummy_logger = logging.getLogger("dummy")
    mocker.patch("promptflow._telemetry.telemetry.get_telemetry_logger", return_value=dummy_logger)
    return


@pytest.fixture
def single_worker_thread_pool() -> None:
    def single_worker_thread_pool_executor(*args, **kwargs):
        return ThreadPoolExecutor(max_workers=1)

    with patch(
        "promptflow.azure.operations._run_operations.ThreadPoolExecutor",
        new=single_worker_thread_pool_executor,
    ):
        yield


@pytest.fixture
def mock_set_headers_with_user_aml_token(mocker: MockerFixture) -> None:
    mocker.patch("promptflow.azure._restclient.flow_service_caller.FlowServiceCaller._set_headers_with_user_aml_token")
    return
