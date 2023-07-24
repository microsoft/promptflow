import re
import sys
from pathlib import Path

import pytest

from promptflow.contracts.error_codes import FlowRequestDeserializeError
from promptflow.contracts.run_info import Status
from promptflow.contracts.run_mode import RunMode
from promptflow.contracts.runtime import SubmitFlowRequest
from promptflow.exceptions import ValidationException
from promptflow.executor import FlowExecutionCoodinator
from promptflow.utils.dataclass_serializer import deserialize_flow_run_info, deserialize_node_run_info
from promptflow_test.utils import convert_request_to_raw, load_and_convert_to_raw, load_json

TEST_ROOT = Path(__file__).parent.parent.parent
JSON_DATA_ROOT = TEST_ROOT / "test_configs/executor_wrong_requests"

if TEST_ROOT not in sys.path:
    sys.path.insert(0, str(TEST_ROOT.absolute()))


@pytest.mark.usefixtures("use_secrets_config_file", "basic_executor")
@pytest.mark.e2etest
class TestExecutorError:
    @pytest.mark.parametrize(
        "file_name, message",
        [
            (
                "no_connection.json",
                "Connection 'wrong_config' is not found, available connection keys [].",
            ),
            (
                "no_connection_param.json",
                "Connection 'bing_wrong_config' is not found, available connection keys [].",
            ),
            (
                "no_provider.json",
                "Please select connection for LLM node 'title_generation'.",
            ),
            (
                "wrong_tool.json",
                "Node 'convert_to_label' references tool 'val_to_label' which is not in the flow 'basic_eval_flow'.",
            ),
            (
                "wrong_tool_variants.json",
                "Node 'convert_to_label' of variant 'variant1' references tool 'val_to_label2' which is not provided.",
            ),
            (
                "wrong_variant_node.json",
                "Node 'convert_to_label2' of variant 'variant1' is not in the flow.",
            ),
            (
                "node_reference.json",
                "Node 'convert_to_label' references node 'other_node' which is not in the flow 'basic_eval_flow'.",
            ),
            ("node_cycle.json", "There is a circular dependency in the flow 'basic_eval_flow'."),
            ("no_input.json", "Inputs in the request of flow 'dummy_qna' is empty."),
            (
                "duplicated_node.json",
                "Node name 'ensure_type_flow' is duplicated in the flow 'ensure_type_conversion'.",
            ),
            (
                "output_wrong_reference.json",
                "Output 'str_val' references node 'ensure_type' which is not in the flow 'ensure_type_conversion'.",
            ),
            (
                "input_wrong_reference.json",
                "Node 'ensure_type_flow' references flow input 'no' which is not in the flow 'ensure_type_conversion'.",
            ),
            (
                "invalid_type/flow_input_int.json",
                "Input 'int' in line 0 for flow 'ensure_type_conversion' of value 0.1 is not type int.",
            ),
            (
                "invalid_type/flow_input_double.json",
                "Input 'double' in line 0 for flow 'ensure_type_conversion' of value z0.1 is not type double.",
            ),
            (
                "invalid_type/flow_input_bool.json",
                "Input 'bool' in line 1 for flow 'ensure_type_conversion' of value truez is not type bool.",
            ),
            (
                "invalid_type/flow_input_bool1.json",
                "Input 'bool' in line 0 for flow 'ensure_type_conversion' of value 123 is not type bool.",
            ),
            (
                "invalid_type/node_input_int.json",
                "Input 'i' for node 'ensure_type_node' of value 0.123 is not type int.",
            ),
            (
                "invalid_type/node_input_double.json",
                "Input 'd' for node 'ensure_type_node' of value z0.1 is not type double.",
            ),
            (
                "invalid_type/node_input_bool.json",
                "Input 'b' for node 'ensure_type_node' of value truez is not type bool.",
            ),
            (
                "invalid_type/node_input_bool1.json",
                "Input 'b' for node 'ensure_type_node' of value 123 is not type bool.",
            ),
            (
                "invalid_type/llm_invalid_connection_type.json",
                "Invalid connection 'bing_connection' type 'BingConnection' for node 'infer_intent', "
                "valid types ['AzureOpenAIConnection'].",
            ),
            (
                "invalid_type/python_invalid_connection_type.json",
                "Input 'connection' for node 'Bing_search' of type 'AzureOpenAIConnection' is not supported, "
                "valid types ['BingConnection', 'OpenAIConnection'].",
            ),
        ],
    )
    def test_executor_submission_error(self, basic_executor: FlowExecutionCoodinator, file_name, message):
        json_file = JSON_DATA_ROOT / file_name
        request_data = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem)
        # TODO: Mock the MT behavior, root runs get pre-created before executor receive the flow request
        self.assert_request_invalid(basic_executor, request_data, message)

    def assert_request_invalid(self, basic_executor: FlowExecutionCoodinator, request, message):
        with pytest.raises(ValidationException) as exc:
            basic_executor.exec_request_raw(raw_request=request)
        ex = exc.value
        assert message == str(ex), f"Expected message {message} but got {str(ex)}"

    @pytest.mark.parametrize(
        "reference, message",
        [
            ("", "Output 'output' is empty."),
            ("${}", "Output 'output' references node '' which is not in the flow 'dummy_qna'."),
            ("${aaa.bbb}", "Output 'output' references node 'aaa' which is not in the flow 'dummy_qna'."),
            ("$", None),
        ],
    )
    def test_executor_flow_output_error(
        self,
        basic_executor: FlowExecutionCoodinator,
        reference,
        message,
    ):
        json_file = JSON_DATA_ROOT / "empty_flow_output.json"
        request = load_json(json_file)
        request["flow"]["outputs"]["output"]["reference"] = reference
        request_raw = convert_request_to_raw(request, json_file.stem)
        request_raw = SubmitFlowRequest.deserialize(request_raw)
        if message:
            self.assert_request_invalid(basic_executor, request_raw, message)
        else:
            # If no error message, it should be valid
            basic_executor.exec_request_raw(request_raw, raise_ex=True)

    @pytest.mark.parametrize(
        "file_name, message, run_mode",
        [
            ("wrong_eval_req.json", "Failed to deserialize EvalRequest due to 'bulk_test_flow_run_ids'.", RunMode.Eval),
            ("wrong_nodes_req.json", "Failed to deserialize NodesRequest due to 'node_name'.", RunMode.SingleNode),
        ],
    )
    def test_executor_deserialize_error(self, basic_executor: FlowExecutionCoodinator, file_name, message, run_mode):
        json_file = JSON_DATA_ROOT / file_name
        with pytest.raises(FlowRequestDeserializeError) as exc:
            request_data = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem, run_mode=run_mode)
            basic_executor.exec_request_raw(raw_request=request_data)
        ex = exc.value
        assert message == str(ex), f"Expected message {message} but got {str(ex)}"

    def test_raw_request_type_error(self, basic_executor: FlowExecutionCoodinator):
        with pytest.raises(ValidationException) as exc:
            basic_executor.exec_request_raw(raw_request="abc")
        ex = exc.value
        assert "Raw request must be 'SubmitFlowRequest' type" in str(ex), f"Expected message but got {str(ex)}"

    @pytest.mark.parametrize(
        "file_name, message",
        [
            (
                "wrong_provider.json",
                "The API 'AzureOpenAI.completionx' is not found.",
            ),
        ],
    )
    def test_executor_start_run_error(self, basic_executor: FlowExecutionCoodinator, file_name, message):
        json_file = JSON_DATA_ROOT / file_name
        request_data = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem)
        with pytest.raises(ValidationException) as exc:
            basic_executor.exec_request_raw(raw_request=request_data)
        ex = exc.value
        assert message == str(ex), f"Expected message {message} but got {str(ex)}"

    @pytest.mark.parametrize(
        "file_name, message",
        [
            (
                "null_connection.json",
                "Required inputs ['connection'] are not provided for tool 'AzureOpenAI.completion'.",
            ),
            (
                "null_connection2.json",
                "Required inputs ['connection'] are not provided for tool 'Bing.search'.",
            ),
            (
                "null_connection_param.json",
                "Required inputs ['connection'] are not provided for tool 'Bing.search'.",
            ),
        ],
    )
    def test_create_executor_error(self, basic_executor: FlowExecutionCoodinator, file_name, message):
        json_file = JSON_DATA_ROOT / file_name
        request_data = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem)
        result = basic_executor.exec_request_raw(raw_request=request_data)
        assert isinstance(result, dict)
        assert "flow_runs" in result
        assert isinstance(result["flow_runs"], list)
        assert 1 == len(result["flow_runs"]), f"Expected 1 flow run but got {len(result['flow_runs'])}"
        # There 0 node run because the flow failed because executor create failed.
        assert 0 == len(result["node_runs"]), f"Expected 1 node run but got {len(result['node_runs'])}"
        root_run = deserialize_flow_run_info(result["flow_runs"][0])
        assert Status.Failed == root_run.status, f"Expected status {Status.Failed} but got {root_run.status}"
        message_in_run = root_run.error["message"]
        assert message_in_run == message, f"Expected message {message} but got {message_in_run}"

    @pytest.mark.parametrize(
        "file_name, message, isFullErrorMessage",
        [
            (
                "output_non_json.json",
                "Flow run failed due to the error: Flow output must be json serializable, dump json failed: "
                "Object of type A is not JSON serializable",
                True,
            ),
            (
                "property_reference.json",
                "Flow run failed due to the error: Invalid node reference: "
                "Invalid property aaa for the node convert_to_label",
                True,
            ),
            (
                "wrong_openai_key.json",
                r"Flow run failed due to the error: OpenAI API hits AuthenticationError.*Error reference: "
                r"https://platform.openai.com/docs/guides/error-codes/api-errors.*",
                False,
            ),
            (
                "tool_code_raises_exception.json",
                "Flow run failed due to the error: Execution failure in 'dummy_search_1': "
                "(ZeroDivisionError) division by zero",
                True,
            ),
        ],
    )
    def test_executor_run_error(self, basic_executor: FlowExecutionCoodinator, file_name, message, isFullErrorMessage):
        json_file = JSON_DATA_ROOT / file_name
        request_data = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem)
        result = basic_executor.exec_request_raw(raw_request=request_data)
        assert isinstance(result, dict)
        assert "flow_runs" in result
        assert isinstance(result["flow_runs"], list)
        assert 2 == len(result["flow_runs"]), f"Expected 2 flow run but got {len(result['flow_runs'])}"
        # There 1 node run because the flow failed before the second node run
        assert 1 == len(result["node_runs"]), f"Expected 1 node run but got {len(result['node_runs'])}"
        root_run = deserialize_flow_run_info(result["flow_runs"][0])
        assert Status.Failed == root_run.status, f"Expected status {Status.Failed} but got {root_run.status}"
        message_in_run = root_run.error["message"]
        if isFullErrorMessage:
            assert message_in_run == message, f"Expected message {message} but got {message_in_run}"
        else:
            re.match(message, message_in_run), f"Pattern not match, Expected message {message} but got {message_in_run}"

    def test_executor_single_node_fail(self, basic_executor: FlowExecutionCoodinator):
        """Make sure exceptions raised in node run execution will not terminate execution process and properly
        recorded in response.
        """
        file_name = "single_node_fail.json"
        json_file = JSON_DATA_ROOT / file_name
        request_data = load_and_convert_to_raw(
            source=json_file, source_run_id=json_file.stem, run_mode=RunMode.SingleNode
        )
        result = basic_executor.exec_request_raw(raw_request=request_data)
        assert 1 == len(result["node_runs"]), f"Expected 1 node run but got {len(result['node_runs'])}"
        run_info = deserialize_node_run_info(result["node_runs"][0])
        assert run_info.error["message"] == "Execution failure in 'extract_1': (Exception) "

    def test_single_node_missing_inputs(self, basic_executor: FlowExecutionCoodinator):
        file_name = "node_mode_missing_inputs.json"
        json_file = JSON_DATA_ROOT / file_name
        request_data = load_and_convert_to_raw(
            source=json_file, source_run_id=json_file.stem, run_mode=RunMode.SingleNode
        )
        with pytest.raises(ValidationException) as exc:
            basic_executor.exec_request_raw(raw_request=request_data)
        assert "Missing node inputs: Bing_search_1, flow.profile, extract_1, inputs.deployment_name" in str(exc.value)

    def test_single_node_reduce(self, basic_executor: FlowExecutionCoodinator):
        file_name = "node_mode_reduce.json"
        json_file = JSON_DATA_ROOT / file_name
        request_data = load_and_convert_to_raw(
            source=json_file, source_run_id=json_file.stem, run_mode=RunMode.SingleNode
        )

        with pytest.raises(ValidationException) as exc:
            basic_executor.exec_request_raw(raw_request=request_data)
        assert "Aggregation node does not support single node run." in str(exc.value)
