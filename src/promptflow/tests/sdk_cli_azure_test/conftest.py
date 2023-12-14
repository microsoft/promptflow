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
from azure.core.exceptions import ResourceNotFoundError
from pytest_mock import MockerFixture

from promptflow._sdk._constants import FlowType
from promptflow.azure import PFClient
from promptflow.azure._entities._flow import Flow

from ._azure_utils import get_cred
from .recording_utilities import (
    PFAzureIntegrationTestRecording,
    SanitizedValues,
    get_pf_client_for_replay,
    is_live,
    is_replay,
)

FLOWS_DIR = "./tests/test_configs/flows"
DATAS_DIR = "./tests/test_configs/datas"
AZUREML_RESOURCE_PROVIDER = "Microsoft.MachineLearningServices"
RESOURCE_ID_FORMAT = "/subscriptions/{}/resourceGroups/{}/providers/{}/workspaces/{}"


@pytest.fixture
def user_object_id() -> str:
    if is_replay():
        return ""
    credential = get_cred()
    access_token = credential.get_token("https://management.azure.com/.default")
    decoded_token = jwt.decode(access_token.token, options={"verify_signature": False})
    return decoded_token["oid"]


@pytest.fixture
def tenant_id() -> str:
    if is_replay():
        return ""
    credential = get_cred()
    access_token = credential.get_token("https://management.azure.com/.default")
    decoded_token = jwt.decode(access_token.token, options={"verify_signature": False})
    return decoded_token["tid"]


@pytest.fixture
def ml_client(
    subscription_id: str,
    resource_group_name: str,
    workspace_name: str,
):
    """return a machine learning client using default e2e testing workspace"""
    from azure.ai.ml import MLClient

    return MLClient(
        credential=get_cred(),
        subscription_id=subscription_id,
        resource_group_name=resource_group_name,
        workspace_name=workspace_name,
        cloud="AzureCloud",
    )


@pytest.fixture
def remote_client(subscription_id: str, resource_group_name: str, workspace_name: str):
    from promptflow.azure import PFClient

    if is_replay():
        yield get_pf_client_for_replay()
    else:
        yield PFClient(
            credential=get_cred(),
            subscription_id=subscription_id,
            resource_group_name=resource_group_name,
            workspace_name=workspace_name,
        )


@pytest.fixture()
def remote_workspace_resource_id(subscription_id: str, resource_group_name: str, workspace_name: str) -> str:
    return "azureml:" + RESOURCE_ID_FORMAT.format(
        subscription_id, resource_group_name, AZUREML_RESOURCE_PROVIDER, workspace_name
    )


@pytest.fixture()
def pf(remote_client):
    # do not add annotation here, because PFClient will trigger promptflow.azure imports and break the isolation
    # between azure and non-azure tests
    yield remote_client


@pytest.fixture
def remote_web_classification_data(remote_client):
    from azure.ai.ml.entities import Data

    data_name, data_version = "webClassification1", "1"
    try:
        return remote_client.ml_client.data.get(name=data_name, version=data_version)
    except ResourceNotFoundError:
        return remote_client.ml_client.data.create_or_update(
            Data(name=data_name, version=data_version, path=f"{DATAS_DIR}/webClassification1.jsonl", type="uri_file")
        )


@pytest.fixture
def runtime(runtime_name: str) -> str:
    return runtime_name


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


@pytest.fixture
def vcr_recording(
    request: pytest.FixtureRequest, user_object_id: str, tenant_id: str
) -> PFAzureIntegrationTestRecording:
    """Fixture to record or replay network traffic.

    If the test mode is "record" or "replay", this fixture will locate a YAML (recording) file
    based on the test file, class and function name, write to (record) or read from (replay) the file.
    """
    recording = PFAzureIntegrationTestRecording.from_test_case(
        test_class=request.cls,
        test_func_name=request.node.name,
        user_object_id=user_object_id,
        tenant_id=tenant_id,
    )
    if not is_live():
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
@pytest.fixture(autouse=not is_live())
def mock_appinsights_log_handler(mocker: MockerFixture) -> None:
    dummy_logger = logging.getLogger("dummy")
    mocker.patch("promptflow._sdk._telemetry.telemetry.get_telemetry_logger", return_value=dummy_logger)
    return


@pytest.fixture
def single_worker_thread_pool() -> None:
    """Mock to use one thread for thread pool executor.

    VCR.py cannot record network traffic in other threads, and we have multi-thread operations
    during resolving the flow. Mock it using one thread to make VCR.py work.
    """

    def single_worker_thread_pool_executor(*args, **kwargs):
        return ThreadPoolExecutor(max_workers=1)

    if is_live():
        yield
    else:
        with patch(
            "promptflow.azure.operations._run_operations.ThreadPoolExecutor",
            new=single_worker_thread_pool_executor,
        ):
            yield


@pytest.fixture
def mock_set_headers_with_user_aml_token(mocker: MockerFixture) -> None:
    """Mock set aml-user-token operation.

    There will be requests fetching cloud metadata during retrieving AML token, which will break during replay.
    As the logic comes from azure-ai-ml, changes in Prompt Flow can hardly affect it, mock it here.
    """
    if not is_live():
        mocker.patch(
            "promptflow.azure._restclient.flow_service_caller.FlowServiceCaller._set_headers_with_user_aml_token"
        )
    yield


@pytest.fixture
def mock_get_azure_pf_client(mocker: MockerFixture, remote_client) -> None:
    """Mock PF Azure client to avoid network traffic during replay test."""
    if not is_live():
        mocker.patch(
            "promptflow._cli._pf_azure._run._get_azure_pf_client",
            return_value=remote_client,
        )
        mocker.patch(
            "promptflow._cli._pf_azure._flow._get_azure_pf_client",
            return_value=remote_client,
        )
    yield


@pytest.fixture
def mock_get_user_identity_info(mocker: MockerFixture) -> None:
    """Mock get user object id and tenant id, currently used in flow list operation."""
    if not is_live():
        mocker.patch(
            "promptflow.azure._restclient.flow_service_caller.FlowServiceCaller._get_user_identity_info",
            return_value=(SanitizedValues.USER_OBJECT_ID, SanitizedValues.TENANT_ID),
        )
    yield


@pytest.fixture
def created_flow(pf: PFClient, randstr: Callable[[str], str]) -> Flow:
    """Create a flow for test."""
    flow_display_name = randstr("flow_display_name")
    flow_source = FLOWS_DIR + "/simple_hello_world/"
    description = "test flow description"
    tags = {"owner": "sdk-test"}
    result = pf.flows.create_or_update(
        flow=flow_source, display_name=flow_display_name, type=FlowType.STANDARD, description=description, tags=tags
    )
    remote_flow_dag_path = result.path

    # make sure the flow is created successfully
    assert pf.flows._storage_client._check_file_share_file_exist(remote_flow_dag_path) is True
    assert result.display_name == flow_display_name
    assert result.type == FlowType.STANDARD
    assert result.tags == tags
    assert result.path.endswith(f"/promptflow/{flow_display_name}/flow.dag.yaml")

    yield result


@pytest.fixture(autouse=not is_live())
def mock_vcrpy_for_httpx() -> None:
    # there is a known issue in vcrpy handling httpx response: https://github.com/kevin1024/vcrpy/pull/591
    # the related code change has not been merged, so we need such a fixture for patch
    def _transform_headers(httpx_response):
        out = {}
        for key, var in httpx_response.headers.raw:
            decoded_key = key.decode("utf-8")
            decoded_var = var.decode("utf-8")
            if decoded_key.lower() == "content-encoding" and decoded_var in ("gzip", "deflate"):
                continue
            out.setdefault(decoded_key, [])
            out[decoded_key].append(decoded_var)
        return out

    with patch("vcr.stubs.httpx_stubs._transform_headers", new=_transform_headers):
        yield


@pytest.fixture(autouse=not is_live())
def mock_to_thread() -> None:
    # https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread
    # to_thread actually uses a separate thread, which will break mocks
    # so we need to mock it to avoid using a separate thread
    # this is only for AsyncRunDownloader.to_thread
    async def to_thread(func, /, *args, **kwargs):
        func(*args, **kwargs)

    with patch(
        "promptflow.azure.operations._async_run_downloader.to_thread",
        new=to_thread,
    ):
        yield
