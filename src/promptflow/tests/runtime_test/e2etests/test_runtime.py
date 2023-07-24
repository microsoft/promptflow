import json
import os
import uuid
from pathlib import Path
from tempfile import mkdtemp
from unittest.mock import Mock, patch

import pytest
from azure.ai.ml import MLClient

from promptflow._constants import PromptflowEdition
from promptflow.contracts.flow import BatchFlowRequest, EvalRequest, Flow
from promptflow.contracts.run_mode import RunMode
from promptflow.contracts.runtime import BatchDataInput, SubmitFlowRequest
from promptflow.exceptions import ExceptionPresenter, JsonSerializedPromptflowException, UserErrorException
from promptflow.runtime.data import _http_to_wsabs_url
from promptflow.runtime.runtime import PromptFlowRuntime, load_runtime_config
from promptflow.runtime.utils._mlclient_helper import MLFLOW_TRACKING_URI_ENV
from promptflow.runtime.utils._utils import get_logger, get_workspace_config

from .._azure_utils import get_azure_blob_service_client, get_cred, get_or_create_data, upload_data
from .._utils import assert_run_completed, get_config_file, get_runtime_config, read_json_file, write_csv
from ..conftest import EXECUTOR_REQUESTS_ROOT

TEST_STORAGE_ACCOUNT = "promptfloweast4063704120"
MASTER_STORAGE_ACCOUNT = "promptflowmast8754379800"
CANARY_STORAGE_ACCOUNT = "promptflowcana4560041206"


logger = get_logger(__name__)


def upload_files_to_blob(local_files, storage_account=TEST_STORAGE_ACCOUNT, container_name="testdata"):
    cred = get_cred()
    result = []
    for local_file in local_files:
        # ensure data exists in remote storage
        client = get_azure_blob_service_client(
            storage_account_name=storage_account, container_name=container_name, credential=cred
        )
        uri = upload_data(local_file, client)
        result.append(uri)
    return result


def mark_run_cancel_requested(run_id: str, mlflow_helper):
    from mlflow.utils.rest_utils import http_request

    cred = mlflow_helper.client._tracking_client.store.get_host_creds()
    cred.host = cred.host.replace("mlflow/v2.0", "mlflow/v1.0").replace("mlflow/v1.0", "history/v1.0")
    http_request(
        host_creds=cred,
        endpoint="/experiments/{}/runs/{}/events".format("Default", run_id),
        method="POST",
        json={"name": "Microsoft.MachineLearning.Run.CancelRequested", "data": {}},
    )


@pytest.fixture
def aml_runtime_config(ml_client: MLClient):
    config = get_workspace_config(ml_client=ml_client, logger=logger)

    runtime_config = get_runtime_config(
        args=[
            "deployment.edition=enterprise",
            f'deployment.mt_service_endpoint={config["mt_service_endpoint"]}',
            f'deployment.subscription_id={config["subscription_id"]}',
            f'deployment.resource_group={config["resource_group"]}',
            f'deployment.workspace_name={config["workspace_name"]}',
            f'deployment.workspace_id={config["workspace_id"]}',
            f'storage.storage_account={config["storage_account"]}',
        ]
    )
    yield runtime_config


@pytest.fixture
def mlflow_helper(ml_client: MLClient):
    from promptflow.storage.azureml_run_storage import MlflowHelper
    from promptflow.utils.utils import get_mlflow_tracking_uri

    ws = ml_client.workspaces.get()
    mt_service_endpoint = ws.discovery_url.replace("/discovery", "")
    tracking_uri = get_mlflow_tracking_uri(
        subscription_id=ml_client.subscription_id,
        resource_group_name=ml_client.resource_group_name,
        workspace_name=ml_client.workspace_name,
        mt_endpoint=mt_service_endpoint,
    )
    yield MlflowHelper(
        mlflow_tracking_uri=tracking_uri,
    )


@pytest.mark.usefixtures("use_secrets_config_file")
@pytest.mark.e2etest
class TestRuntime:
    def test_runtime_flow(self, ml_client: MLClient):
        file_path = get_config_file(root=EXECUTOR_REQUESTS_ROOT, file="qa_with_bing.json")
        bfr = BatchFlowRequest.deserialize(read_json_file(file_path))
        # make sure batch_inputs is empty, so we can test the runtime data resolve feature
        bfr.batch_inputs = []
        assert bfr is not None

        batch_inputs_file = get_config_file(file="requests/qa_with_bing.csv")

        data_name = "qa_with_bing_test_data"
        data = get_or_create_data(ml_client, data_name, batch_inputs_file)

        # pass to user code so user code can resolve the ws info
        request = SubmitFlowRequest(
            flow_id="qa_with_bing",
            flow_run_id=str(uuid.uuid4()),
            run_mode=RunMode.Flow,
            submission_data=bfr,
            batch_data_input=BatchDataInput(data_uri=f"azureml:{data.id}"),
        )
        assert len(request.submission_data.batch_inputs) == 0
        runtime_config = get_runtime_config()
        # runtime_config.execution.execute_in_process = True
        runtime = PromptFlowRuntime(runtime_config)
        result = runtime.execute(request)
        assert_run_completed(result)
        assert len(result["flow_runs"]) == 2
        assert result["flow_runs"][1]["inputs"] == {"question": "When did OpenAI announced their chatgpt api?"}

    def test_runtime_flow_with_invalid_data(self, invalid_data):
        file_path = get_config_file(root=EXECUTOR_REQUESTS_ROOT, file="qa_with_bing.json")
        bfr = BatchFlowRequest.deserialize(read_json_file(file_path))
        # make sure batch_inputs is empty, so we can test the runtime data resolve feature
        bfr.batch_inputs = []
        assert bfr is not None

        # pass to user code so user code can resolve the ws info
        request = SubmitFlowRequest(
            flow_id="qa_with_bing",
            flow_run_id=str(uuid.uuid4()),
            run_mode=RunMode.Flow,
            submission_data=bfr,
            batch_data_input=BatchDataInput(data_uri=f"azureml:{invalid_data.id}"),
        )
        assert len(request.submission_data.batch_inputs) == 0
        runtime_config = get_runtime_config()
        # runtime_config.execution.execute_in_process = True
        runtime = PromptFlowRuntime(runtime_config)
        try:
            runtime.execute(request)
        except JsonSerializedPromptflowException as e:
            # request should fail with exception
            expected_error_dict = {
                "code": "UserError",
                "message": "Fail to load invalid data. We support file formats: csv, tsv, json, jsonl, parquet. "
                "Please check input data.",
                "messageFormat": "Fail to load invalid data. We support file formats: csv, tsv, json, jsonl, parquet. "
                "Please check input data.",
                "messageParameters": {},
                "referenceCode": "Runtime",
                "innerError": {
                    "code": "InvalidUserData",
                    "innerError": None,
                },
            }

            error_dict = json.loads(e.message)
            assert error_dict == expected_error_dict

            error_dict = ExceptionPresenter(e).to_dict()
            assert error_dict == expected_error_dict

    def test_runtime_bulk_test(self, ml_client: MLClient):
        file_path = get_config_file(root=EXECUTOR_REQUESTS_ROOT, file="flow_with_eval.json")
        bfr = BatchFlowRequest.deserialize(read_json_file(file_path))
        # make sure batch_inputs is empty, so we can test the runtime data resolve feature
        bfr.batch_inputs = []
        assert bfr is not None

        batch_inputs_file = get_config_file(file="flows/flow_with_eval/batch_input.jsonl")

        data_name = "flow_with_eval_test_data"
        data = get_or_create_data(ml_client, data_name, batch_inputs_file)

        # pass to user code so user code can resolve the ws info
        request = SubmitFlowRequest(
            flow_id="evaluator_flow",
            flow_run_id=str(uuid.uuid4()),
            run_mode=RunMode.BulkTest,
            submission_data=bfr,
            batch_data_input=BatchDataInput(data_uri=data.path),
        )
        runtime_config = get_runtime_config()
        runtime = PromptFlowRuntime(runtime_config)
        result = runtime.execute(request)
        assert_run_completed(result)

        # test invalid input
        invalid_request = SubmitFlowRequest(
            flow_id="evaluator_flow",
            flow_run_id=str(uuid.uuid4()),
            run_mode=RunMode.BulkTest,
            submission_data=bfr,
            batch_data_input=BatchDataInput(data_uri="invalid"),
        )
        runtime_config = get_runtime_config()
        assert runtime_config.execution.execute_in_process is False
        runtime = PromptFlowRuntime(runtime_config)
        try:
            runtime.execute(invalid_request)
        except JsonSerializedPromptflowException as e:
            # request should fail with exception
            error_dict = json.loads(e.message)
            assert error_dict == {
                "code": "UserError",
                "message": "Invalid data uri: invalid",
                "messageFormat": "Invalid data uri: {uri}",
                "messageParameters": {"uri": "invalid"},
                "referenceCode": "Runtime",
                "innerError": {"code": "InvalidDataUri", "innerError": None},
            }

    def test_runtime_eval_flow(self, ml_client: MLClient):
        file_path = get_config_file(root=EXECUTOR_REQUESTS_ROOT, file="eval_existing_run.json")
        er = EvalRequest.deserialize(read_json_file(file_path))
        # make sure batch_inputs is empty, so we can test the runtime data resolve feature
        er.bulk_test_inputs = []
        assert er is not None

        batch_inputs_file = get_config_file(file="flows/eval_existing_run/batch_input.jsonl")

        data_name = "eval_existing_run_test_data"
        data = get_or_create_data(ml_client, data_name, batch_inputs_file)

        # pass to user code so user code can resolve the ws info
        request = SubmitFlowRequest(
            flow_id="eval_existing_run",
            flow_run_id=str(uuid.uuid4()),
            run_mode=RunMode.Eval,
            submission_data=er,
            bulk_test_data_input=BatchDataInput(data_uri=data.path),
        )
        runtime_config = get_runtime_config()
        runtime = PromptFlowRuntime(runtime_config)
        try:
            result = runtime.execute(request)
        except JsonSerializedPromptflowException as e:
            # expected failure with RunInfoNotFoundInStorageError
            error_dict = json.loads(e.message)
            error_message = (
                "Error of 'LocalRunStorage': Flow run not found. "
                "run id: 13531690-3ec7-4129-a527-708f54909757_variant0."
            )
            assert error_dict == {
                "code": "SystemError",
                "message": error_message,
                "messageFormat": "",
                "messageParameters": {},
                "referenceCode": "RunStorage",
                "innerError": {
                    "code": "RunStorageError",
                    "innerError": {
                        "code": "RunInfoNotFoundInStorageError",
                        "innerError": None,
                    },
                },
            }
        else:
            run = result["flow_runs"][0]
            assert run["status"] == "Completed"

        # test invalid input
        invalid_request = SubmitFlowRequest(
            flow_id="eval_existing_run",
            flow_run_id=str(uuid.uuid4()),
            run_mode=RunMode.Eval,
            submission_data=er,
            bulk_test_data_input=BatchDataInput(data_uri="invalid path"),
        )
        runtime_config = get_runtime_config()
        runtime = PromptFlowRuntime(runtime_config)

        try:
            runtime.execute(invalid_request)
        except JsonSerializedPromptflowException as e:
            # request should fail with exception
            error_dict = json.loads(e.message)
            assert error_dict == {
                "code": "UserError",
                "message": "Invalid data uri: invalid path",
                "messageFormat": "Invalid data uri: {uri}",
                "messageParameters": {"uri": "invalid path"},
                "referenceCode": "Runtime",
                "innerError": {"code": "InvalidDataUri", "innerError": None},
            }

    def test_batch_inputs_flow(self, ml_client: MLClient, aml_runtime_config):
        file_path = get_config_file("flows/batch_inputs/flow.json")
        flow = Flow.deserialize(read_json_file(file_path))
        assert flow is not None

        local_files = [
            get_config_file("flows/batch_inputs/data/batch_input1.csv"),
            get_config_file("flows/batch_inputs/data/batch_input2.csv"),
        ]
        urls = upload_files_to_blob(local_files, storage_account=CANARY_STORAGE_ACCOUNT)

        batch_inputs = []
        for idx, url in enumerate(urls):
            input = {"uri": _http_to_wsabs_url(url), "data_asset_name": f"test_batch_input_flow_{idx}"}
            batch_inputs.append(input)
        batch_inputs_file = get_config_file("flows/batch_inputs/batch_inputs.csv")
        write_csv(batch_inputs, batch_inputs_file)

        data_name = "bach_input_test_data"
        data = get_or_create_data(ml_client, data_name, batch_inputs_file)

        # pass to user code so user code can resolve the ws info
        envs = {
            "SUBSCRIPTION_ID": ml_client.subscription_id,
            "RESOURCE_GROUP": ml_client.resource_group_name,
            "WORKSPACE_NAME": ml_client.workspace_name,
        }

        bfr = BatchFlowRequest(flow=flow, connections={}, batch_inputs=[])
        request = SubmitFlowRequest(
            flow_id="batch_inputs_flow",
            flow_run_id=str(uuid.uuid4()),
            run_mode=RunMode.Flow,
            submission_data=bfr,
            environment_variables=envs,
            batch_data_input=BatchDataInput(data_uri=f"azureml:{data.name}:{data.version}"),
        )
        runtime = PromptFlowRuntime(aml_runtime_config)
        result = runtime.execute(request)
        assert_run_completed(result)

    def test_customize_token_flow(self, aml_runtime_config):
        file_path = get_config_file("flows/environment_variables/flow.json")
        flow = Flow.deserialize(read_json_file(file_path))
        assert flow is not None
        bfr = BatchFlowRequest(flow=flow, connections={}, batch_inputs=[{"env_key": "TESTHOME"}])

        cred = get_cred()
        # audience = "https://storage.azure.com"
        audience = "https://management.azure.com"
        token = cred.get_token(audience).token

        request = SubmitFlowRequest(
            flow_id="environment_variables_flow",
            flow_run_id=str(uuid.uuid4()),
            run_mode=RunMode.Flow,
            # flow = flow,
            submission_data=bfr,
            workspace_msi_token_for_storage_resource=token,
            environment_variables={"TESTHOME": "123"},
        )

        with patch.dict(os.environ, {MLFLOW_TRACKING_URI_ENV: f"azureml:{aml_runtime_config.deployment.workspace_id}"}):
            runtime = PromptFlowRuntime(aml_runtime_config)
            result = runtime.execute(request)
            assert_run_completed(result)

    def test_envrionment_variables_flow(self):
        file_path = get_config_file("flows/environment_variables/flow.json")
        flow = Flow.deserialize(read_json_file(file_path))
        assert flow is not None
        env_key = "abc"
        env_val = "def"
        bfr = BatchFlowRequest(flow=flow, connections={}, batch_inputs=[{"env_key": env_key}])

        # not setting environment variables should fail
        if env_key in os.environ:
            os.environ.pop(env_key)
        request = SubmitFlowRequest(
            flow_id="environment_variables_flow",
            flow_run_id=str(uuid.uuid4()),
            run_mode=RunMode.Flow,
            # flow = flow,
            submission_data=bfr,
            environment_variables={},
        )

        runtime = PromptFlowRuntime(get_runtime_config())
        result = runtime.execute(request)

        assert result is not None
        assert "flow_runs" in result, f"get invalid result: {result}"
        assert result["flow_runs"][0]["status"] == "Failed"

        # setting environment variables should success
        if env_key in os.environ:
            os.environ.pop(env_key)
        request = SubmitFlowRequest(
            flow_id="environment_variables_flow",
            flow_run_id=str(uuid.uuid4()),
            run_mode=RunMode.Flow,
            # flow = flow,
            submission_data=bfr,
            environment_variables={env_key: env_val},
        )

        runtime = PromptFlowRuntime(get_runtime_config())
        result = runtime.execute(request)
        assert_run_completed(result)
        # assert run["result"]["env_value"][0] == env_val

    def test_chat_flow(self):
        file_path = get_config_file("flows/chat_flow/flow.json")
        bfr = BatchFlowRequest.deserialize(read_json_file(file_path))
        # For chat flow, input is a list/json string concatenated by UI so can't be a workspace dataset.
        assert bfr is not None
        request = SubmitFlowRequest(
            flow_id="chat_flow",
            flow_run_id=str(uuid.uuid4()),
            run_mode=RunMode.Flow,
            submission_data=bfr,
        )
        runtime_config = get_runtime_config()
        runtime = PromptFlowRuntime(runtime_config)
        result = runtime.execute(request)
        assert_run_completed(result)

    def test_runtime_config_not_init_when_making_request(self):
        # Compute not authenticate when init config
        with patch("promptflow.runtime.utils._mlclient_helper.get_mlclient_from_env", return_value=None):
            config = load_runtime_config()
            # make this config enterprise
            config.deployment.edition = "enterprise"
            assert config is not None
            assert not config.deployment.subscription_id
            assert not config.deployment.resource_group
            assert not config.deployment.workspace_name
            assert not config.deployment.mt_service_endpoint

            # compute not authenticated when making requests
            assert config.execution.execute_in_process is False
            with patch("promptflow.runtime.runtime.execute_request_multiprocessing", return_value=None):
                runtime = PromptFlowRuntime(config)
                # raise exception to guide user to authenticate
                with pytest.raises(UserErrorException) as e:
                    runtime.execute(Mock())
                assert "please authenticate if running in component instance" in str(e.value)

    def test_runtime_config_init_when_making_request(self, ml_client: MLClient):
        # Compute not authenticate when init config
        with patch("promptflow.runtime.utils._mlclient_helper.get_mlclient_from_env") as mock_client:
            mock_client.return_value = None
            config = load_runtime_config()
            config.deployment.edition = PromptflowEdition.ENTERPRISE
            assert config is not None
            assert not config.deployment.subscription_id
            assert not config.deployment.resource_group
            assert not config.deployment.workspace_name
            assert not config.deployment.mt_service_endpoint

            mock_client.return_value = ml_client
            assert config.execution.execute_in_process is False
            # compute authenticated when making requests
            with patch("promptflow.runtime.runtime.execute_request_multiprocessing", return_value=None):
                runtime = PromptFlowRuntime(config)
                runtime.execute(Mock())

                # config is ready when making requests
                assert config is not None
                assert config.deployment.subscription_id
                assert config.deployment.resource_group
                assert config.deployment.workspace_name
                assert config.deployment.mt_service_endpoint

    def test_runtime_bulk_log(self):
        file_path = get_config_file(root=EXECUTOR_REQUESTS_ROOT, file="variants_flow_with_eval_collection.json")
        bfr = BatchFlowRequest.deserialize(read_json_file(file_path))
        flow_run_id = str(uuid.uuid4())
        request = SubmitFlowRequest(
            flow_id="variants_flow_with_eval_collection",
            flow_run_id=flow_run_id,
            run_mode=RunMode.BulkTest,
            submission_data=bfr,
        )
        eval_flow_run_id = str(uuid.uuid4())
        bulk_test_run_id = str(uuid.uuid4())
        variant_run_1_id = str(uuid.uuid4())
        variant_run_2_id = str(uuid.uuid4())

        submission_data = request.submission_data
        submission_data.bulk_test_id = bulk_test_run_id
        submission_data.eval_flow_run_id = eval_flow_run_id
        submission_data.variants_runs["variant1"] = variant_run_1_id
        submission_data.variants_runs["variant2"] = variant_run_2_id

        run_id_to_log_file = {
            request.flow_run_id: str(Path(mkdtemp()) / f"{flow_run_id}.log"),
            variant_run_1_id: str(Path(mkdtemp()) / f"{variant_run_1_id}.log"),
            variant_run_2_id: str(Path(mkdtemp()) / f"{variant_run_2_id}.log"),
            eval_flow_run_id: str(Path(mkdtemp()) / f"{eval_flow_run_id}.log"),
        }

        request.run_id_to_log_path = run_id_to_log_file

        runtime_config = get_runtime_config()
        # Test multiprocessing case.
        runtime_config.execution.execute_in_process = False
        runtime = PromptFlowRuntime(runtime_config)
        result = runtime.execute(request)
        assert_run_completed(result)

        # Make sure logs contain expected contents.
        total_line_number = len(submission_data.batch_inputs)
        for run_id, log_file_path in run_id_to_log_file.items():
            with open(log_file_path, "r") as f:
                log = f.read()
            # Make sure logs by bulk logger in executor.
            assert f"Finished 1 / {total_line_number} lines." in log
            # Make sure logs by runtime in root flow run.
            if run_id == flow_run_id:
                assert "Start processing flow" in log
                assert "Start execute request" in log
