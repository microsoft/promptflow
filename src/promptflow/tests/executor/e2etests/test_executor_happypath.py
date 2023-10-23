import uuid
import os
from types import GeneratorType

import pytest

from promptflow._utils.dataclass_serializer import serialize
from promptflow.contracts.run_info import FlowRunInfo
from promptflow.contracts.run_info import RunInfo as NodeRunInfo
from promptflow.contracts.run_info import Status
from promptflow.exceptions import UserErrorException
from promptflow.executor import FlowExecutor
from promptflow.executor._errors import ConnectionNotFound, InputTypeError, ResolveToolError
from promptflow.executor.flow_executor import BulkResult, LineResult
from promptflow.storage import AbstractRunStorage

from ..utils import (
    FLOW_ROOT,
    get_flow_expected_metrics,
    get_flow_expected_status_summary,
    get_flow_sample_inputs,
    get_yaml_file,
    get_yaml_working_dir
)

SAMPLE_FLOW = "web_classification_no_variants"
SAMPLE_EVAL_FLOW = "classification_accuracy_evaluation"
SAMPLE_FLOW_WITH_PARTIAL_FAILURE = "python_tool_partial_failure"
SAMPLE_FLOW_WITH_LANGCHAIN_TRACES = "flow_with_langchain_traces"


class MemoryRunStorage(AbstractRunStorage):
    def __init__(self):
        self._node_runs = {}
        self._flow_runs = {}

    def persist_flow_run(self, run_info: FlowRunInfo):
        self._flow_runs[run_info.run_id] = run_info

    def persist_node_run(self, run_info: NodeRunInfo):
        self._node_runs[run_info.run_id] = run_info


@pytest.mark.usefixtures("use_secrets_config_file", "dev_connections")
@pytest.mark.e2etest
class TestExecutor:
    def get_line_inputs(self, flow_folder=""):
        if flow_folder:
            inputs = self.get_bulk_inputs(flow_folder)
            return inputs[0]
        return {
            "url": "https://www.apple.com/shop/buy-iphone/iphone-14",
            "text": "some_text",
        }

    def get_bulk_inputs(self, nlinee=4, flow_folder="", sample_inputs_file="", return_dict=False):
        if flow_folder:
            if not sample_inputs_file:
                sample_inputs_file = "samples.json"
            inputs = get_flow_sample_inputs(flow_folder, sample_inputs_file=sample_inputs_file)
            if isinstance(inputs, list) and len(inputs) > 0:
                return inputs
            elif isinstance(inputs, dict):
                if return_dict:
                    return inputs
                return [inputs]
            else:
                raise Exception(f"Invalid type of bulk input: {inputs}")
        return [self.get_line_inputs() for _ in range(nlinee)]

    def skip_serp(self, flow_folder, dev_connections):
        serp_required_flows = ["package_tools"]
        #  Real key is usually more than 32 chars
        serp_key = dev_connections.get("serp_connection", {"value": {"api_key": ""}})["value"]["api_key"]
        if flow_folder in serp_required_flows and len(serp_key) < 32:
            pytest.skip("serp_connection is not prepared")

    def test_executor_storage(self, dev_connections):
        mem_run_storage = MemoryRunStorage()
        executor = FlowExecutor.create(
            get_yaml_file("web_classification_no_variants"),
            dev_connections,
            storage=mem_run_storage,
        )
        run_id = str(uuid.uuid4())
        bulk_inputs = self.get_bulk_inputs()
        nlines = len(bulk_inputs)
        bulk_result = executor.exec_bulk(bulk_inputs, run_id)
        msg = f"Only {len(bulk_result.line_results)}/{nlines} lines are returned."
        assert len(bulk_result.line_results) == nlines, msg
        for line_result in bulk_result.line_results:
            flow_run_info = line_result.run_info
            msg = f"Flow run {flow_run_info.run_id} is not persisted in memory storage."
            assert flow_run_info.run_id in mem_run_storage._flow_runs, msg
            for node_name, node_run_info in line_result.node_run_infos.items():
                msg = f"Node run {node_run_info.run_id} is not persisted in memory storage."
                assert node_run_info.run_id in mem_run_storage._node_runs, msg
                run_info_in_mem = mem_run_storage._node_runs[node_run_info.run_id]
                assert serialize(node_run_info) == serialize(run_info_in_mem)
                msg = f"Node run name {node_run_info.node} is not correct, expected {node_name}"
                assert mem_run_storage._node_runs[node_run_info.run_id].node == node_name

    @pytest.mark.parametrize(
        "flow_folder",
        [
            SAMPLE_FLOW,
            "prompt_tools",
            "script_with___file__",
            "connection_as_input",
        ],
    )
    def test_executor_exec_bulk(self, flow_folder, dev_connections):
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections, raise_ex=True)
        run_id = str(uuid.uuid4())
        bulk_inputs = self.get_bulk_inputs()
        nlines = len(bulk_inputs)
        bulk_results = executor.exec_bulk(bulk_inputs, run_id)
        assert isinstance(bulk_results, BulkResult)
        msg = f"Bulk result only has {len(bulk_results.line_results)}/{nlines} outputs"
        assert len(bulk_results.outputs) == nlines, msg
        for i, output in enumerate(bulk_results.outputs):
            assert isinstance(output, dict)
            assert "line_number" in output, f"line_number is not in {i}th output {output}"
            assert output["line_number"] == i, f"line_number is not correct in {i}th output {output}"
        msg = f"Bulk result only has {len(bulk_results.line_results)}/{nlines} line results"
        assert len(bulk_results.outputs) == nlines, msg
        for i, line_result in enumerate(bulk_results.line_results):
            assert isinstance(line_result, LineResult)
            assert line_result.run_info.status == Status.Completed, f"{i}th line got {line_result.run_info.status}"

    def test_executor_exec_bulk_then_eval(self, dev_connections):
        classification_executor = FlowExecutor.create(get_yaml_file(SAMPLE_FLOW), dev_connections, raise_ex=True)
        bulk_inputs = self.get_bulk_inputs()
        nlines = len(bulk_inputs)
        bulk_results = classification_executor.exec_bulk(bulk_inputs)
        assert len(bulk_results.outputs) == len(bulk_inputs)
        eval_executor = FlowExecutor.create(get_yaml_file(SAMPLE_EVAL_FLOW), dev_connections, raise_ex=True)
        input_dicts = {"data": bulk_inputs, "run.outputs": bulk_results.outputs}
        inputs_mapping = {
            "variant_id": "baseline",
            "groundtruth": "${data.url}",
            "prediction": "${run.outputs.category}",
        }
        mapped_inputs = eval_executor.validate_and_apply_inputs_mapping(input_dicts, inputs_mapping)
        result = eval_executor.exec_bulk(mapped_inputs)
        assert len(result.outputs) == nlines, f"Only {len(result.outputs)}/{nlines} outputs are returned."
        assert len(result.metrics) > 0, "No metrics are returned."
        assert result.metrics["accuracy"] == 0, f"Accuracy should be 0, got {result.metrics}."

    def test_executor_exec_bulk_with_metrics(self, dev_connections):
        flow_folder = SAMPLE_EVAL_FLOW
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections, raise_ex=True)
        run_id = str(uuid.uuid4())
        bulk_inputs = self.get_bulk_inputs(flow_folder=flow_folder)
        bulk_results = executor.exec_bulk(bulk_inputs, run_id)
        assert isinstance(bulk_results, BulkResult)
        assert isinstance(bulk_results.metrics, dict)
        assert bulk_results.metrics == get_flow_expected_metrics(flow_folder)
        status_summary = bulk_results.get_status_summary()
        assert status_summary == get_flow_expected_status_summary(flow_folder)

    def test_executor_exec_bulk_with_partial_failure(self, dev_connections):
        flow_folder = SAMPLE_FLOW_WITH_PARTIAL_FAILURE
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections, raise_ex=False)
        run_id = str(uuid.uuid4())
        bulk_inputs = self.get_bulk_inputs(flow_folder=flow_folder)
        bulk_results = executor.exec_bulk(bulk_inputs, run_id)
        assert isinstance(bulk_results, BulkResult)
        status_summary = bulk_results.get_status_summary()
        assert status_summary == get_flow_expected_status_summary(flow_folder)

    def test_executor_exec_bulk_with_line_number(self, dev_connections):
        flow_folder = SAMPLE_FLOW_WITH_PARTIAL_FAILURE
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections, raise_ex=False)
        run_id = str(uuid.uuid4())
        bulk_inputs = self.get_bulk_inputs(flow_folder=flow_folder, sample_inputs_file="inputs.json", return_dict=True)
        bulk_inputs_mapping = self.get_bulk_inputs(
            flow_folder=flow_folder, sample_inputs_file="inputs_mapping.json", return_dict=True
        )
        resolved_inputs = executor.validate_and_apply_inputs_mapping(bulk_inputs, bulk_inputs_mapping)
        bulk_results = executor.exec_bulk(resolved_inputs, run_id)
        assert isinstance(bulk_results, BulkResult)
        assert len(bulk_results.outputs) == 2
        assert bulk_results.outputs == [
            {"line_number": 0, "output": 1},
            {"line_number": 6, "output": 7},
        ]

    # TODO: Add test for flow with langchain traces
    def test_executor_exec_bulk_with_openai_metrics(self, dev_connections):
        classification_executor = FlowExecutor.create(get_yaml_file(SAMPLE_FLOW), dev_connections, raise_ex=True)
        bulk_inputs = self.get_bulk_inputs()
        bulk_results = classification_executor.exec_bulk(bulk_inputs)
        assert len(bulk_results.outputs) == len(bulk_inputs)
        openai_metrics = bulk_results.get_openai_metrics()
        assert "total_tokens" in openai_metrics
        assert openai_metrics["total_tokens"] > 0

    @pytest.mark.parametrize(
        "flow_folder",
        [
            SAMPLE_FLOW,
            "prompt_tools",
            "script_with___file__",
            "script_with_import",
            "package_tools",
            "connection_as_input",
            "python_tool_with_multiple_image_nodes"
        ],
    )
    def test_executor_exec_line(self, flow_folder, dev_connections):
        self.skip_serp(flow_folder, dev_connections)
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)
        flow_result = executor.exec_line(self.get_line_inputs())
        assert not executor._run_tracker._flow_runs, "Flow runs in run tracker should be empty."
        assert not executor._run_tracker._node_runs, "Node runs in run tracker should be empty."
        assert isinstance(flow_result.output, dict)
        assert flow_result.run_info.status == Status.Completed
        node_count = len(executor._flow.nodes)
        assert isinstance(flow_result.run_info.api_calls, list) and len(flow_result.run_info.api_calls) == node_count
        assert len(flow_result.node_run_infos) == node_count
        for node, node_run_info in flow_result.node_run_infos.items():
            assert node_run_info.status == Status.Completed
            assert node_run_info.node == node
            assert isinstance(node_run_info.api_calls, list)  # api calls is set

    @pytest.mark.parametrize(
        "flow_folder, node_name, flow_inputs, dependency_nodes_outputs",
        [
            ("web_classification_no_variants", "summarize_text_content", {}, {"fetch_text_content_from_url": "Hello"}),
            ("prompt_tools", "summarize_text_content_prompt", {"text": "text"}, {}),
            ("script_with___file__", "node1", {"text": "text"}, None),
            ("script_with___file__", "node2", None, {"node1": "text"}),
            ("script_with___file__", "node3", None, None),
            ("package_tools", "search_by_text", {"text": "elon mask"}, None),  # Skip since no api key in CI
            ("connection_as_input", "conn_node", None, None),
            ("simple_aggregation", "accuracy", {"text": "A"}, {"passthrough": "B"}),
            ("script_with_import", "node1", {"text": "text"}, None),
        ],
    )
    def test_executor_exec_node(self, flow_folder, node_name, flow_inputs, dependency_nodes_outputs, dev_connections):
        self.skip_serp(flow_folder, dev_connections)
        yaml_file = get_yaml_file(flow_folder)
        working_dir = get_yaml_working_dir(flow_folder)
        os.chdir(working_dir)
        run_info = FlowExecutor.load_and_exec_node(
            yaml_file,
            node_name,
            flow_inputs=flow_inputs,
            dependency_nodes_outputs=dependency_nodes_outputs,
            connections=dev_connections,
            raise_ex=True,
        )
        assert run_info.output is not None
        assert run_info.status == Status.Completed
        assert isinstance(run_info.api_calls, list)
        assert run_info.node == node_name
        assert run_info.system_metrics["duration"] >= 0

    @pytest.mark.parametrize(
        "flow_folder, node_name, flow_inputs, dependency_nodes_outputs",
        [
            ("python_tool_with_multiple_image_nodes", "python_node_2", {"logo_content": "Microsoft and four squares"},
             {"python_node": {"image": {"data:image/jpg;path": "logo.jpg"}, "image_name": "Microsoft's logo",
                              "image_list": [{"data:image/jpg;path": "logo.jpg"}]}}),
            ("python_tool_with_multiple_image_nodes", "python_node", {
             "image": "logo.jpg", "image_name": "Microsoft's logo"}, {},)
        ],
    )
    def test_executor_exec_with_image_node(self, flow_folder, node_name, flow_inputs, dependency_nodes_outputs,
                                           dev_connections):
        self.skip_serp(flow_folder, dev_connections)
        yaml_file = get_yaml_file(flow_folder)
        working_dir = get_yaml_working_dir(flow_folder)
        os.chdir(working_dir)
        run_info = FlowExecutor.load_and_exec_node(
            yaml_file,
            node_name,
            flow_inputs=flow_inputs,
            dependency_nodes_outputs=dependency_nodes_outputs,
            connections=dev_connections,
            output_relative_path_dir=("./temp"),
            raise_ex=True,
        )
        assert "data:image/jpg;path" and "temp" in str(run_info.output)
        assert run_info.status == Status.Completed
        assert isinstance(run_info.api_calls, list)
        assert run_info.node == node_name
        assert run_info.system_metrics["duration"] >= 0

    def test_executor_node_overrides(self, dev_connections):
        inputs = self.get_line_inputs()
        executor = FlowExecutor.create(
            get_yaml_file(SAMPLE_FLOW),
            dev_connections,
            node_override={"classify_with_llm.deployment_name": "dummy_deployment"},
            raise_ex=True,
        )
        with pytest.raises(UserErrorException) as e:
            executor.exec_line(inputs)
        assert type(e.value).__name__ == "WrappedOpenAIError"
        assert "The API deployment for this resource does not exist." in str(e.value)

        with pytest.raises(ResolveToolError) as e:
            executor = FlowExecutor.create(
                get_yaml_file(SAMPLE_FLOW),
                dev_connections,
                node_override={"classify_with_llm.connection": "dummy_connection"},
                raise_ex=True,
            )
        assert isinstance(e.value.inner_exception, ConnectionNotFound)
        assert "Connection 'dummy_connection' not found" in str(e.value)

    @pytest.mark.parametrize(
        "flow_folder",
        [
            "no_inputs_outputs",
        ],
    )
    def test_flow_with_no_inputs_and_output(self, flow_folder, dev_connections):
        executor = FlowExecutor.create(get_yaml_file(flow_folder, FLOW_ROOT), dev_connections)
        flow_result = executor.exec_line({})
        assert flow_result.output == {}
        assert flow_result.run_info.status == Status.Completed
        node_count = len(executor._flow.nodes)
        assert isinstance(flow_result.run_info.api_calls, list) and len(flow_result.run_info.api_calls) == node_count
        assert len(flow_result.node_run_infos) == node_count
        for node, node_run_info in flow_result.node_run_infos.items():
            assert node_run_info.status == Status.Completed
            assert node_run_info.node == node
            assert isinstance(node_run_info.api_calls, list)  # api calls is set

    @pytest.mark.parametrize(
        "flow_folder",
        [
            "simple_flow_with_python_tool",
        ],
    )
    def test_convert_flow_input_types(self, flow_folder, dev_connections) -> None:
        executor = FlowExecutor.create(get_yaml_file(flow_folder, FLOW_ROOT), dev_connections)
        ret = executor.convert_flow_input_types(inputs={"num": "11"})
        assert ret == {"num": 11}
        ret = executor.convert_flow_input_types(inputs={"text": "12", "num": "11"})
        assert ret == {"text": "12", "num": 11}
        with pytest.raises(InputTypeError):
            ret = executor.convert_flow_input_types(inputs={"num": "hello"})
            executor.convert_flow_input_types(inputs={"num": "hello"})

    def test_chat_flow_stream_mode(self, dev_connections) -> None:
        executor = FlowExecutor.create(get_yaml_file("python_stream_tools", FLOW_ROOT), dev_connections)

        # To run a flow with stream output, we need to set this flag to run tracker.
        # TODO: refine the interface

        inputs = {"text": "hello", "chat_history": []}
        line_result = executor.exec_line(inputs, allow_generator_output=True)

        # Assert there's only one output
        assert len(line_result.output) == 1
        assert set(line_result.output.keys()) == {"output_echo"}

        # Assert the only output is a generator
        output_echo = line_result.output["output_echo"]
        assert isinstance(output_echo, GeneratorType)
        assert list(output_echo) == ["Echo: ", "hello "]

        # Assert the flow is completed and no errors are raised
        flow_run_info = line_result.run_info
        assert flow_run_info.status == Status.Completed
        assert flow_run_info.error is None

    @pytest.mark.parametrize(
        "flow_folder",
        [
            "web_classification",
        ],
    )
    def test_executor_creation_with_default_variants(self, flow_folder, dev_connections):
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)
        flow_result = executor.exec_line(self.get_line_inputs())
        assert flow_result.run_info.status == Status.Completed

    def test_executor_creation_with_default_input(self):
        # Assert for single node run.
        default_input_value = "input value from default"
        yaml_file = get_yaml_file("default_input")
        executor = FlowExecutor.create(yaml_file, {})
        node_result = executor.load_and_exec_node(yaml_file, "test_print_input")
        assert node_result.status == Status.Completed
        assert node_result.output == default_input_value

        # Assert for flow run.
        flow_result = executor.exec_line({})
        assert flow_result.run_info.status == Status.Completed
        assert flow_result.output["output"] == default_input_value
        aggr_results = executor.exec_aggregation({}, aggregation_inputs={})
        flow_aggregate_node = aggr_results.node_run_infos["aggregate_node"]
        assert flow_aggregate_node.status == Status.Completed
        assert flow_aggregate_node.output == [default_input_value]

        # Assert for bulk run.
        bulk_result = executor.exec_bulk([{}])
        assert bulk_result.line_results[0].run_info.status == Status.Completed
        assert bulk_result.line_results[0].output["output"] == default_input_value
        bulk_aggregate_node = bulk_result.aggr_results.node_run_infos["aggregate_node"]
        assert bulk_aggregate_node.status == Status.Completed
        assert bulk_aggregate_node.output == [default_input_value]

        # Assert for exec
        exec_result = executor.exec({})
        assert exec_result["output"] == default_input_value

    @pytest.mark.parametrize(
        "flow_folder, batch_input, expected_type, validate_inputs",
        [
            ("simple_aggregation", [{"text": 4}], str, True),
            ("simple_aggregation", [{"text": 4.5}], str, True),
            ("simple_aggregation", [{"text": "3.0"}], str, True),
            ("simple_aggregation", [{"text": 4}], int, False),
        ],
    )
    def test_bulk_run_line_result(self, flow_folder, batch_input, expected_type, validate_inputs, dev_connections):
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)
        bulk_result = executor.exec_bulk(
            batch_input,
            validate_inputs=validate_inputs,
        )
        assert type(bulk_result.line_results[0].run_info.inputs["text"]) is expected_type
