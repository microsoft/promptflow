import os
import pytest
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import mkdtemp

from azure.storage.blob import AccountSasPermissions, BlobClient, BlobServiceClient, generate_blob_sas
from promptflow._constants import STORAGE_ACCOUNT_NAME, PromptflowEdition
from promptflow.contracts.run_mode import RunMode
from promptflow.runtime.runtime import get_log_context
from promptflow.utils.credential_scrubber import CredentialScrubber
from promptflow.utils.utils import _get_default_credential
from promptflow_test.unittests.test_log_manager import assert_datetime_prefix
from promptflow_test.utils import load_and_convert_to_raw

TEST_ROOT = Path(__file__).parent.parent.parent
JSON_DATA_ROOT = TEST_ROOT / "test_configs/executor_api_requests"

if TEST_ROOT not in sys.path:
    sys.path.insert(0, str(TEST_ROOT.absolute()))


def get_connection_dict():
    return {
        "azure_open_ai_connection": {
            "type": "AzureOpenAIConnection",
            "value": {
                "api_key": "azure-openai-key",
                "api_base": "https://gpt-test-eus.openai.azure.com/",
                "api_type": "azure",
                "api_version": "2023-03-15-preview",
            },
        },
        "bing_connection": {
            "type": "BingConnection",
            "value": {
                "api_key": "bing-key",
                "url": "https://api.bing.microsoft.com/v7.0/search",
            },
            "module": "promptflow.connections",
        },
    }


@pytest.mark.usefixtures("use_secrets_config_file", "basic_executor", "local_executor")
@pytest.mark.e2etest
@pytest.mark.flaky(reruns=3, reruns_delay=1)
class TestLogs:
    @pytest.mark.usefixtures("set_azureml_config")
    def test_executor_logs_flow_mode_enterprise(self, basic_executor) -> None:
        file_name = "batch_request_e2e.json"
        node_name = "extract_from_bing_result"  # Check logs of this tool.
        json_file = Path(JSON_DATA_ROOT) / file_name
        request_data = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem)
        # Replace customer code to add print/logging for test
        submission_data = request_data.submission_data
        tools = submission_data.flow.tools
        for t in tools:
            if t.name == node_name:
                original_code = t.code
                target_str = "def extract_from_bing_result(result_str: str) -> dict:\n"
                index_to_insert = original_code.index(target_str) + len(target_str)
                new_code = (
                    "    import sys\n"
                    + "    print('test stdout')\n"  # noqa: W504
                    + "    print('test stderr', file=sys.stderr)\n"  # noqa: W504
                    + "    import logging\n"  # noqa: W504
                    + "    logger = logging.getLogger('test logger')\n"  # noqa: W504
                    + "    if len(logger.handlers) == 0:"  # noqa: W504
                    "        logger.addHandler(logging.StreamHandler(stream=sys.stdout))\n"
                    + "    logger.warning('test logger')\n"  # noqa: W504, E501
                )
                code = original_code[:index_to_insert] + new_code + original_code[index_to_insert:]
                t.code = code

        # Only keep one input.
        submission_data.batch_inputs = [submission_data.batch_inputs[0]]

        # Add flow_run_id_to_log_path to submission data.
        root_flow_run_id = request_data.flow_run_id
        credential = _get_default_credential()
        storage_account_name = os.environ.get(STORAGE_ACCOUNT_NAME)
        log_sas_uri = _generate_log_blob_sas_uri(storage_account_name, root_flow_run_id, credential)
        run_id_to_log_file = {
            root_flow_run_id: log_sas_uri,
        }
        request_data.run_id_to_log_path = run_id_to_log_file

        # Execute request.
        with get_log_context(request_data, PromptflowEdition.ENTERPRISE):
            result = basic_executor.exec_request_raw(raw_request=request_data, raise_ex=True)

        # Check node run logs.
        for run in result["node_runs"]:
            assert run["status"] == "Completed"
            if run["node"] == node_name:
                # Assert stdout
                output = run["logs"].get("stdout")
                outputs = output.split("\n")
                assert_datetime_prefix(outputs[0], "test stdout")
                assert_datetime_prefix(outputs[1], "test logger")
                assert outputs[2] == ""
                # Assert stderr
                assert_datetime_prefix(run["logs"].get("stderr"), "test stderr\n")

        # Check flow run log.
        log = _get_log_from_sas_uri(log_sas_uri)
        # Check node run logs in root flow log file.
        assert "test stdout" in log
        assert "test logger" in log
        assert "test stderr" in log
        # Make sure logs contain expected contents.
        assert "Executing node" in log
        # Bulk log should not be included in logs of flow mode.
        assert "Finished 1 / 1 lines" not in log

    def test_executor_logs_bulk_mode_community(self, local_executor) -> None:
        file_name = "variants_flow_with_eval_collection.json"
        json_file = Path(JSON_DATA_ROOT) / file_name
        request_data = load_and_convert_to_raw(
            source=json_file, source_run_id=json_file.stem, run_mode=RunMode.BulkTest
        )

        # Change bulk test id and eval_flow_run_id.
        request = request_data.submission_data
        eval_flow_run_id = str(uuid.uuid4())
        bulk_test_run_id = str(uuid.uuid4())
        request.bulk_test_id = bulk_test_run_id
        request.eval_flow_run_id = eval_flow_run_id

        # Set variant run ids.
        variant_run_1_id = str(uuid.uuid4())
        variant_run_2_id = str(uuid.uuid4())
        request.variants_runs["variant1"] = variant_run_1_id
        request.variants_runs["variant2"] = variant_run_2_id

        # Add flow_run_id_to_log_path to submission data.
        root_flow_run_id = request_data.flow_run_id
        run_id_to_log_file = {
            root_flow_run_id: str(Path(mkdtemp()) / f"{root_flow_run_id}.log"),
            variant_run_1_id: str(Path(mkdtemp()) / f"{variant_run_1_id}.log"),
            variant_run_2_id: str(Path(mkdtemp()) / f"{variant_run_2_id}.log"),
            eval_flow_run_id: str(Path(mkdtemp()) / f"{eval_flow_run_id}.log"),
        }
        request_data.run_id_to_log_path = run_id_to_log_file

        # Execute request.
        with get_log_context(request_data, PromptflowEdition.COMMUNITY):
            _ = local_executor.exec_request_raw(raw_request=request_data, raise_ex=True)

        # Make sure logs contain expected contents.
        total_line_number = len(request.batch_inputs)
        for run_id, log_file_path in run_id_to_log_file.items():
            with open(log_file_path, "r") as f:
                log = f.read()
            assert f"Finished 1 / {total_line_number} lines." in log
            # Flow log should not be included in logs of bulk mode.
            assert "Executing node" not in log

    def test_executor_logs_flow_mode_community(self, local_executor) -> None:
        file_name = "qa_with_bing.json"
        json_file = Path(JSON_DATA_ROOT) / file_name
        request_data = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem, run_mode=RunMode.Flow)
        # Add flow_run_id_to_log_path to request data.
        root_flow_run_id = request_data.flow_run_id
        log_file_path = str(Path(mkdtemp()) / f"{root_flow_run_id}.log")
        run_id_to_log_file = {
            root_flow_run_id: log_file_path,
        }
        request_data.run_id_to_log_path = run_id_to_log_file

        # Execute request.
        with get_log_context(request_data, PromptflowEdition.COMMUNITY):
            _ = local_executor.exec_request_raw(raw_request=request_data, raise_ex=True)

        # Make sure logs contain expected contents.
        with open(log_file_path, "r") as f:
            log = f.read()
        assert "Executing node" in log, f"Log should contain node run logs, see '{log_file_path}' for details."
        # Bulk log should not be included in logs of flow mode.
        assert "Finished 1 / 1 lines" not in log, \
            f"Log should not contain finish logs, see '{log_file_path}' for details."

    def test_connections_are_scrubbed(self, local_executor):
        file_name = "batch_request_e2e.json"
        tool_name = "extract_from_bing_result"
        json_file = Path(JSON_DATA_ROOT) / file_name
        request_data = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem, run_mode=RunMode.Flow)
        # Add flow_run_id_to_log_path to request data.
        root_flow_run_id = request_data.flow_run_id
        log_file_path = str(Path(mkdtemp()) / f"{root_flow_run_id}.log")
        run_id_to_log_file = {
            root_flow_run_id: log_file_path,
        }
        request_data.run_id_to_log_path = run_id_to_log_file

        submission_data = request_data.submission_data
        # Add dummy connections to submission_data.
        dummy_connection = get_connection_dict()
        submission_data.connections.update(dummy_connection)

        # Replace customer code to deliberately print connection key in log.
        tools = submission_data.flow.tools
        for t in tools:
            if t.name == tool_name:
                original_code = t.code
                target_str = "def extract_from_bing_result(result_str: str) -> dict:\n"
                index_to_insert = original_code.index(target_str) + len(target_str)
                new_code = (
                    "    print('Print aoai key: azure-openai-key')\n"
                    + "    print('Print bing key: bing-key')\n"  # noqa: W504
                    + "    print('Print signature: &sig=secret')\n"  # noqa: W504
                    + "    print('Print key: &key=secret')\n"  # noqa: W504
                )
                code = original_code[:index_to_insert] + new_code + original_code[index_to_insert:]
                t.code = code

        # Execute request.
        with get_log_context(request_data, PromptflowEdition.COMMUNITY):
            _ = local_executor.exec_request_raw(raw_request=request_data, raise_ex=True)

        # Make sure connection key is not shown in log.
        with open(log_file_path, "r") as f:
            log = f.read()
        expected_print_messages = [
            f'Print aoai key: {CredentialScrubber.PLACE_HOLDER}',
            f'Print bing key: {CredentialScrubber.PLACE_HOLDER}',
            f'Print signature: &sig={CredentialScrubber.PLACE_HOLDER}',
            f'Print key: &key={CredentialScrubber.PLACE_HOLDER}',
        ]
        black_list_strings = [
            'azure-openai-key',
            'bing-key',
            'secret',
        ]
        for m in expected_print_messages:
            assert m in log

        for s in black_list_strings:
            assert s not in log


def _generate_log_blob_sas_uri(account_name: str, flow_run_id: str, credential):
    container_name = "flow-run-tests"
    blob_name = flow_run_id + ".txt"
    blob_account_url = blob_account_url = f"https://{account_name}.blob.core.windows.net"
    blob_service_client = BlobServiceClient(blob_account_url, credential=credential)
    user_delegation_key = blob_service_client.get_user_delegation_key(
        key_start_time=datetime.utcnow() - timedelta(minutes=10),
        key_expiry_time=datetime.utcnow() + timedelta(minutes=10),
    )
    blob_client = blob_service_client.get_blob_client(container_name, blob_name)

    # Create container and an empty blob client.
    container_client = blob_service_client.get_container_client(container_name)
    if not container_client.exists():
        blob_service_client.create_container(container_name)
    blob_client.upload_blob("", blob_type="AppendBlob")

    sas_token = generate_blob_sas(
        account_name,
        container_name,
        blob_name,
        permission=AccountSasPermissions(read=True, write=True),
        expiry=datetime.utcnow() + timedelta(hours=1),
        user_delegation_key=user_delegation_key,
    )

    return blob_client.url + "?" + sas_token


def _get_log_from_sas_uri(sas_uri) -> str:
    blob_client = BlobClient.from_blob_url(sas_uri)
    return blob_client.download_blob().readall().decode()
