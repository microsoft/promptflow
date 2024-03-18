# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional
from unittest.mock import patch

import jwt
import pytest
from azure.core.exceptions import ResourceNotFoundError
from mock import mock
from pytest_mock import MockerFixture

from promptflow._sdk._constants import FlowType, RunStatus
from promptflow._sdk.entities import Run
from promptflow._utils.user_agent_utils import ClientUserAgentUtil
from promptflow.azure import PFClient
from promptflow.azure._entities._flow import Flow

from ._azure_utils import get_cred
from .recording_utilities import (
    PFAzureIntegrationTestRecording,
    SanitizedValues,
    VariableRecorder,
    get_created_flow_name_from_flow_path,
    get_pf_client_for_replay,
    is_live,
    is_record,
    is_replay,
)

FLOWS_DIR = "./tests/test_configs/flows"
EAGER_FLOWS_DIR = "./tests/test_configs/eager_flows"
DATAS_DIR = "./tests/test_configs/datas"
AZUREML_RESOURCE_PROVIDER = "Microsoft.MachineLearningServices"
RESOURCE_ID_FORMAT = "/subscriptions/{}/resourceGroups/{}/providers/{}/workspaces/{}"


def package_scope_in_live_mode() -> str:
    """Determine the scope of some expected sharing fixtures.

    We have many tests against flows and runs, and it's very time consuming to create a new flow/run
    for each test. So we expect to leverage pytest fixture concept to share flows/runs across tests.
    However, we also have replay tests, which require function scope fixture as it will locate the
    recording YAML based on the test function info.

    Use this function to determine the scope of the fixtures dynamically. For those fixtures that
    will request dynamic scope fixture(s), they also need to be dynamic scope.
    """
    # package-scope should be enough for Azure tests
    return "package" if is_live() else "function"


@pytest.fixture(scope=package_scope_in_live_mode())
def user_object_id() -> str:
    if is_replay():
        return SanitizedValues.USER_OBJECT_ID
    credential = get_cred()
    access_token = credential.get_token("https://management.azure.com/.default")
    decoded_token = jwt.decode(access_token.token, options={"verify_signature": False})
    return decoded_token["oid"]


@pytest.fixture(scope=package_scope_in_live_mode())
def tenant_id() -> str:
    if is_replay():
        return SanitizedValues.TENANT_ID
    credential = get_cred()
    access_token = credential.get_token("https://management.azure.com/.default")
    decoded_token = jwt.decode(access_token.token, options={"verify_signature": False})
    return decoded_token["tid"]


@pytest.fixture(scope=package_scope_in_live_mode())
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


@pytest.fixture(scope=package_scope_in_live_mode())
def remote_client(subscription_id: str, resource_group_name: str, workspace_name: str):
    from promptflow.azure import PFClient

    if is_replay():
        client = get_pf_client_for_replay()
    else:
        client = PFClient(
            credential=get_cred(),
            subscription_id=subscription_id,
            resource_group_name=resource_group_name,
            workspace_name=workspace_name,
        )
    assert "promptflow-sdk" in ClientUserAgentUtil.get_user_agent()
    assert "promptflow-test" not in ClientUserAgentUtil.get_user_agent()
    yield client


@pytest.fixture
def remote_workspace_resource_id(subscription_id: str, resource_group_name: str, workspace_name: str) -> str:
    return "azureml:" + RESOURCE_ID_FORMAT.format(
        subscription_id, resource_group_name, AZUREML_RESOURCE_PROVIDER, workspace_name
    )


@pytest.fixture(scope=package_scope_in_live_mode())
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


@pytest.fixture(scope="session")
def runtime(runtime_name: str) -> str:
    return runtime_name


PROMPTFLOW_ROOT = Path(__file__) / "../../.."
MODEL_ROOT = Path(PROMPTFLOW_ROOT / "tests/test_configs/flows")


@pytest.fixture
def flow_serving_client_remote_connection(mocker: MockerFixture, remote_workspace_resource_id):
    from promptflow.core._serving.app import create_app as create_serving_app

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
def flow_serving_client_with_prt_config_env(
    mocker: MockerFixture, subscription_id, resource_group_name, workspace_name
):  # noqa: E501
    connections = {
        "PRT_CONFIG_OVERRIDE": f"deployment.subscription_id={subscription_id},"
        f"deployment.resource_group={resource_group_name},"
        f"deployment.workspace_name={workspace_name},"
        "app.port=8088",
    }
    return create_serving_client_with_connections("basic-with-connection", mocker, connections)


@pytest.fixture
def flow_serving_client_with_connection_provider_env(mocker: MockerFixture, remote_workspace_resource_id):
    connections = {"PROMPTFLOW_CONNECTION_PROVIDER": remote_workspace_resource_id}
    return create_serving_client_with_connections("basic-with-connection", mocker, connections)


@pytest.fixture
def flow_serving_client_with_aml_resource_id_env(mocker: MockerFixture, remote_workspace_resource_id):
    aml_resource_id = "{}/onlineEndpoints/{}/deployments/{}".format(remote_workspace_resource_id, "myendpoint", "blue")
    connections = {"AML_DEPLOYMENT_RESOURCE_ID": aml_resource_id}
    return create_serving_client_with_connections("basic-with-connection", mocker, connections)


@pytest.fixture
def serving_client_with_connection_name_override(mocker: MockerFixture, remote_workspace_resource_id):
    connections = {
        "aoai_connection": "azure_open_ai_connection",
        "PROMPTFLOW_CONNECTION_PROVIDER": remote_workspace_resource_id,
    }
    return create_serving_client_with_connections("llm_connection_override", mocker, connections)


@pytest.fixture
def serving_client_with_connection_data_override(mocker: MockerFixture, remote_workspace_resource_id):
    model_name = "llm_connection_override"
    model_path = (Path(MODEL_ROOT) / model_name).resolve().absolute()
    # load arm connection template
    connection_arm_template = model_path.joinpath("connection_arm_template.json").read_text()
    connections = {
        "aoai_connection": connection_arm_template,
        "PROMPTFLOW_CONNECTION_PROVIDER": remote_workspace_resource_id,
    }
    return create_serving_client_with_connections(model_name, mocker, connections)


def create_serving_client_with_connections(model_name, mocker: MockerFixture, connections: dict = {}):
    from promptflow.core._serving.app import create_app as create_serving_app

    model_path = (Path(MODEL_ROOT) / model_name).resolve().absolute().as_posix()
    mocker.patch.dict(os.environ, {"PROMPTFLOW_PROJECT_PATH": model_path})
    mocker.patch.dict(
        os.environ,
        {
            **connections,
        },
    )
    # Set credential to None for azureml extension type
    # As we mock app in github workflow, which do not have managed identity credential
    func = "promptflow.core._serving.extension.azureml_extension._get_managed_identity_credential_with_retry"
    with mock.patch(func) as mock_cred_func:
        mock_cred_func.return_value = None
        app = create_serving_app(
            environment_variables={"API_TYPE": "${azure_open_ai_connection.api_type}"},
            extension_type="azureml",
        )
    app.config.update(
        {
            "TESTING": True,
        }
    )
    return app.test_client()


@pytest.fixture(scope=package_scope_in_live_mode())
def variable_recorder() -> VariableRecorder:
    yield VariableRecorder()


@pytest.fixture(scope=package_scope_in_live_mode())
def randstr(variable_recorder: VariableRecorder) -> Callable[[str], str]:
    """Return a "random" UUID."""

    def generate_random_string(variable_name: str) -> str:
        random_string = str(uuid.uuid4())
        if is_live():
            return random_string
        elif is_replay():
            return variable_name
        else:
            return variable_recorder.get_or_record_variable(variable_name, random_string)

    return generate_random_string


@pytest.fixture(scope=package_scope_in_live_mode())
def vcr_recording(
    request: pytest.FixtureRequest, user_object_id: str, tenant_id: str, variable_recorder: VariableRecorder
) -> Optional[PFAzureIntegrationTestRecording]:
    """Fixture to record or replay network traffic.

    If the test mode is "live", nothing will happen.
    If the test mode is "record" or "replay", this fixture will locate a YAML (recording) file
    based on the test file, class and function name, write to (record) or read from (replay) the file.
    """
    if is_live():
        yield None
    else:
        recording = PFAzureIntegrationTestRecording.from_test_case(
            test_class=request.cls,
            test_func_name=request.node.name,
            user_object_id=user_object_id,
            tenant_id=tenant_id,
            variable_recorder=variable_recorder,
        )
        recording.enter_vcr()
        request.addfinalizer(recording.exit_vcr)
        yield recording


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


@pytest.fixture(scope=package_scope_in_live_mode())
def mock_get_user_identity_info(user_object_id: str, tenant_id: str) -> None:
    """Mock get user object id and tenant id, currently used in flow list operation."""
    if not is_live():
        with patch(
            "promptflow.azure._restclient.flow_service_caller.FlowServiceCaller._get_user_identity_info",
            return_value=(user_object_id, tenant_id),
        ):
            yield
    else:
        yield


@pytest.fixture(scope=package_scope_in_live_mode())
def created_flow(pf: PFClient, randstr: Callable[[str], str], variable_recorder: VariableRecorder) -> Flow:
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
    assert result.path.endswith("flow.dag.yaml")

    # flow in Azure will have different file share name with timestamp
    # and this is a client-side behavior, so we need to sanitize this in recording
    # so extract this during record test
    if is_record():
        flow_name_const = "flow_name"
        flow_name = get_created_flow_name_from_flow_path(result.path)
        variable_recorder.get_or_record_variable(flow_name_const, flow_name)

    yield result


@pytest.fixture(scope=package_scope_in_live_mode())
def created_batch_run_without_llm(pf: PFClient, randstr: Callable[[str], str], runtime: str) -> Run:
    """Create a batch run that does not require LLM."""
    name = randstr("batch_run_name")
    run = pf.run(
        # copy test_configs/flows/simple_hello_world to a separate folder
        # as pf.run will generate .promptflow/flow.tools.json
        # it will affect Azure file share upload logic and replay test
        flow=f"{FLOWS_DIR}/hello-world",
        data=f"{DATAS_DIR}/webClassification3.jsonl",
        column_mapping={"name": "${data.url}"},
        name=name,
        display_name="sdk-cli-test-fixture-batch-run-without-llm",
    )
    run = pf.runs.stream(run=name)
    assert run.status == RunStatus.COMPLETED
    yield run


@pytest.fixture(scope=package_scope_in_live_mode())
def simple_eager_run(pf: PFClient, randstr: Callable[[str], str]) -> Run:
    """Create a simple eager run."""
    run = pf.run(
        flow=f"{EAGER_FLOWS_DIR}/simple_with_req",
        data=f"{DATAS_DIR}/simple_eager_flow_data.jsonl",
        name=randstr("name"),
    )
    pf.runs.stream(run)
    run = pf.runs.get(run)
    assert run.status == RunStatus.COMPLETED
    yield run


@pytest.fixture(scope=package_scope_in_live_mode())
def created_eval_run_without_llm(
    pf: PFClient, randstr: Callable[[str], str], runtime: str, created_batch_run_without_llm: Run
) -> Run:
    """Create a evaluation run against batch run without LLM dependency."""
    name = randstr("eval_run_name")
    run = pf.run(
        flow=f"{FLOWS_DIR}/eval-classification-accuracy",
        data=f"{DATAS_DIR}/webClassification3.jsonl",
        run=created_batch_run_without_llm,
        column_mapping={"groundtruth": "${data.answer}", "prediction": "${run.outputs.result}"},
        runtime=runtime,
        name=name,
        display_name="sdk-cli-test-fixture-eval-run-without-llm",
    )
    run = pf.runs.stream(run=name)
    assert run.status == RunStatus.COMPLETED
    yield run


@pytest.fixture(scope=package_scope_in_live_mode())
def created_failed_run(pf: PFClient, randstr: Callable[[str], str], runtime: str) -> Run:
    """Create a failed run."""
    name = randstr("failed_run_name")
    run = pf.run(
        flow=f"{FLOWS_DIR}/partial_fail",
        data=f"{DATAS_DIR}/webClassification3.jsonl",
        runtime=runtime,
        name=name,
        display_name="sdk-cli-test-fixture-failed-run",
    )
    # set raise_on_error to False to promise returning something
    run = pf.runs.stream(run=name, raise_on_error=False)
    assert run.status == RunStatus.FAILED
    yield run


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


@pytest.fixture
def mock_isinstance_for_mock_datastore() -> None:
    """Mock built-in function isinstance.

    We have an isinstance check during run download for datastore type for better error message;
    while our mock datastore in replay mode is not a valid type, so mock it with strict condition.
    """
    if not is_replay():
        yield
    else:
        from azure.ai.ml.entities._datastore.azure_storage import AzureBlobDatastore

        from .recording_utilities.utils import MockDatastore

        original_isinstance = isinstance

        def mock_isinstance(*args):
            if original_isinstance(args[0], MockDatastore) and args[1] == AzureBlobDatastore:
                return True
            return original_isinstance(*args)

        with patch("builtins.isinstance", new=mock_isinstance):
            yield


@pytest.fixture(autouse=True)
def mock_check_latest_version() -> None:
    """Mock check latest version.

    As CI uses docker, it will always trigger this check behavior, and we don't have recording for this;
    and this will hit many unknown issue with vcrpy.
    """
    with patch("promptflow._utils.version_hint_utils.check_latest_version", new=lambda: None):
        yield
