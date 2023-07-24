import json
import logging
from pathlib import Path

import pytest

from promptflow_test.utils import assert_success

from .bulk_run_outputs_validator import BulkRunOutputsValidator
from .endpoint_client import PromptflowEndpointClient

TEST_ROOT = Path(__file__).parent.parent / "test_configs"
E2E_SAMPLES_PATH = TEST_ROOT / "e2e_samples"

FLOW_RUNS_LIST = ["classification_accuracy_eval", "conditional_flow_with_skip"]
FLOW_RUNS_NEED_OPENAI_KEY_LIST = ["flow_need_openai_key_in_env_vars"]
BULK_RUNS_LIST = ["llm_tools", "python_tool_print_input_single_input", "python_tool_print_input_multi_inputs"]
CONNECTION_NAMES_LIST = ["azure_open_ai_connection", "Default_AzureOpenAI"]


@pytest.mark.endpointtest
class TestEndpointV2:
    @pytest.mark.parametrize(
        "folder_name",
        FLOW_RUNS_LIST,
    )
    def test_executor_flow_run(self, endpoint_client: PromptflowEndpointClient, folder_name):
        flow_folder_path = Path(E2E_SAMPLES_PATH) / folder_name
        flow_folder_path = flow_folder_path.resolve().absolute()
        logging.info(f"Submit a flow run with the folder: {flow_folder_path}")
        repsonse = endpoint_client.submit_flow(flow_folder_path)
        logging.info(f"Flow response: {json.dumps(repsonse, indent=4)}")
        assert_success(repsonse)

    @pytest.mark.parametrize(
        "connection_name",
        CONNECTION_NAMES_LIST,
    )
    def test_executor_flow_run_with_env_vars(self, endpoint_client: PromptflowEndpointClient, connection_name):
        flow_folder_path = Path(E2E_SAMPLES_PATH) / "flow_need_openai_key_in_env_vars"
        flow_folder_path = flow_folder_path.resolve().absolute()
        logging.info(f"Submit a flow run with the folder: {flow_folder_path}")
        env_vars = {
            "OPENAI_API_BASE": f"${{{connection_name}.api_base}}",
            "OPENAI_API_KEY": f"${{{connection_name}.api_key}}",
            "OPENAI_API_TYPE": f"${{{connection_name}.api_type}}",
            "OPENAI_API_VERSION": f"${{{connection_name}.api_version}}",
        }
        repsonse = endpoint_client.submit_flow(flow_folder_path, env_vars=env_vars)
        logging.info(f"Flow response: {json.dumps(repsonse, indent=4)}")
        assert_success(repsonse)

    @pytest.mark.parametrize(
        "folder_name",
        BULK_RUNS_LIST,
    )
    def test_executor_bulk_run(self, endpoint_client: PromptflowEndpointClient, folder_name):
        flow_folder_path = Path(E2E_SAMPLES_PATH) / folder_name
        flow_folder_path = flow_folder_path.resolve().absolute()
        logging.info(f"Submit a bulk run with the folder: {flow_folder_path}")
        flow_run_id = endpoint_client.submit_bulk_run(flow_folder_path)
        print(f"flow_run_id: {flow_run_id}")
        logging.info(f"The flow run id of the bulk run is: {flow_run_id}")
        bulk_run_outputs_valiadator = BulkRunOutputsValidator(endpoint_client, flow_folder_path, flow_run_id)
        bulk_run_outputs_valiadator.assert_output_files()
