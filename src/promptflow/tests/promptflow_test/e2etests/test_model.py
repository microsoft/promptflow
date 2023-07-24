import uuid
from pathlib import Path

import pytest

from promptflow.contracts.flow import Flow, InputValueType, Node
from promptflow.contracts.run_info import Status
from promptflow.contracts.tool import Tool
from promptflow.executor import FlowExecutionCoodinator, FlowExecutor
from promptflow.executor.error_codes import InputNotFound
from promptflow.executor.flow_validator import FlowValidator
from promptflow_test.utils import load_json

TEST_ROOT = Path(__file__).parent.parent.parent
MODEL_ROOT = TEST_ROOT / "test_configs/e2e_samples"


@pytest.mark.usefixtures("use_secrets_config_file", "basic_executor")
@pytest.mark.e2etest
class TestModel:
    def resolve_flow_executor(self, model_file: Path, coodinator: FlowExecutionCoodinator, overrides=None):
        connections = {k: v for k, v in coodinator._connections_in_env.items()}
        return coodinator.create_flow_executor_by_model(model_file, connections, node_overrides=overrides)

    @pytest.mark.parametrize(
        "model_file, overrides, expected_connections",
        [
            (
                "llm_tools/flow.dag.yaml",
                {
                    "summarize_text_content_prompt.connection": "azure_open_ai_connection",
                    "summarize_text_content_prompt.deployment_name": "text-davinci-003",
                },
                {"azure_open_ai_connection"},
            ),
            (
                "python_conn_tool/flow.dag.yaml",
                {
                    "python_conn_tool.conn1": "azure_open_ai_connection",
                    "python_conn_tool.conn2": "azure_open_ai_connection",
                    "python_conn_tool.serp_conn": "serp_connection",
                },
                {"azure_open_ai_connection", "serp_connection"},
            ),
        ],
    )
    def test_model_with_override(
        self,
        model_file,
        overrides,
        expected_connections,
        basic_executor: FlowExecutionCoodinator,
    ):
        model_file = MODEL_ROOT / model_file
        connection_names = basic_executor.get_connection_names_from_node_overrides(model_file, overrides)
        assert connection_names == expected_connections
        executor = self.resolve_flow_executor(model_file, basic_executor, overrides)
        flow = executor._flow
        for k, v in overrides.items():
            node_name, input_name = k.split(".")
            node = flow.get_node(node_name)
            if node is None:
                raise ValueError(f"Node {node_name} not found in flow")
            if input_name == "connection":
                assert node.connection == v
            else:
                assignment = node.inputs[input_name]
                connection_name = getattr(assignment.value, "__connection_name", None)
                if connection_name:
                    # Replacing connection
                    assert connection_name == v
                else:
                    # Literal value
                    assert assignment.value == v
                assert assignment.value_type == InputValueType.LITERAL
        output_names = list(executor._flow.outputs.keys())
        samples = load_json(model_file.parent / "inputs.json")
        if isinstance(samples, dict):
            samples = [samples]
        for sample in samples:
            result = executor.exec(sample)
            for name in output_names:
                assert name in result, f"Output {name} not found in result {result}"
                assert result[name] is not None, f"Output {name} is None in result {result}"

    @pytest.mark.parametrize(
        "model_file",
        [
            "qa_with_bing/flow.json",  # Old style
            "qa_with_bing",  # Old style folder
            "script_with_import/flow.dag.yaml",
            "script_with_import",
        ],
    )
    def test_model_basic_flow(self, model_file, basic_executor: FlowExecutionCoodinator) -> None:
        model_file = MODEL_ROOT / model_file
        executor = self.resolve_flow_executor(MODEL_ROOT / model_file, basic_executor)
        output_names = list(executor._flow.outputs.keys())
        model_and_variants_dir = model_file if model_file.is_dir() else model_file.parent
        samples = load_json(MODEL_ROOT / model_and_variants_dir / "inputs.json")
        if isinstance(samples, dict):
            samples = [samples]
        for sample in samples:
            result = executor.exec(sample)
            assert "line_number" not in result, "line_number should not be in result"
            for name in output_names:
                assert name in result, f"Output {name} not found in result {result}"
                assert result[name] is not None, f"Output {name} is None in result {result}"

    @pytest.mark.parametrize(
        "model_dir",
        [
            "prompt_tools",  # Line process only
            "aggregation_complicated_example",  # Line process + aggregation
        ],
    )
    def test_prs_scenario(self, model_dir, basic_executor: FlowExecutionCoodinator):
        executor = self.resolve_flow_executor(MODEL_ROOT / model_dir, basic_executor)
        bulk_inputs = load_json(MODEL_ROOT / model_dir / "bulk_inputs.json")
        inputs_mapping_file = MODEL_ROOT / model_dir / "inputs_mapping.json"
        if inputs_mapping_file.exists():
            inputs_mapping = load_json(inputs_mapping_file)
        else:
            inputs_mapping = executor.default_inputs_mapping  # For the scenario inputs_mapping is not provided
        aggregation_inputs = {key: [] for key in executor._aggregation_inputs_references}
        inputs_as_dict = {i: [] for i in bulk_inputs[0]}  # For aggregation, the inputs should be converted to a dict
        for i, item in enumerate(bulk_inputs):
            item_applying_mapping = FlowExecutor.apply_inputs_mapping_legacy({"data": item}, inputs_mapping)
            line_result = executor.exec_line(item_applying_mapping, i)
            assert line_result.output["line_number"] == i, f"Line number is not correct in {line_result.output}"
            for k, v in line_result.aggregation_inputs.items():
                aggregation_inputs[k].append(v)
            for k, v in inputs_as_dict.items():
                v.append(item[k])
        if not executor.has_aggregation_node:
            return
        inputs_as_dict_applying_mapping = FlowExecutor.apply_inputs_mapping_legacy(
            {"data": inputs_as_dict}, inputs_mapping
        )
        aggr_results = executor.exec_aggregation(inputs_as_dict_applying_mapping, aggregation_inputs)
        metrics = aggr_results.metrics
        assert isinstance(metrics, dict) and len(metrics) > 0, f"Metrics not found: {metrics}"
        for k, v in metrics.items():
            assert isinstance(v, (int, float)), f"Metric {k} is not a numeric value: {v}"
        node_run_infos = aggr_results.node_run_infos
        for node in executor.aggregation_nodes:
            assert node in node_run_infos, f"Aggregation run info {node} not found: {node_run_infos}"
            assert node_run_infos[node].status == Status.Completed, f"Node {node} not succeeded: {node_run_infos[node]}"

    @pytest.mark.parametrize(
        "model_file",
        [
            "script_with_import/flow.dag.yaml",
        ],
    )
    def test_basic_flow_exec_bulk(self, model_file) -> None:
        model_file = MODEL_ROOT / model_file
        executor = FlowExecutor.create(model_file, connections={})
        samples = load_json(MODEL_ROOT / model_file.parent / "inputs.json")
        if isinstance(samples, dict):
            samples = [samples]
        result = executor.exec_bulk(samples)
        outputs = result.outputs
        assert len(outputs) == len(samples), f"Expected {len(samples)} outputs, got {len(outputs)}"
        for output in outputs:
            assert "line_number" in output, f"Output {output} does not have line_number"
        metrics = result.metrics
        assert len(metrics) > 0, f"Metrics not found: {metrics}"
        for k, v in metrics.items():
            assert isinstance(v, (int, float)), f"Metric {k} is not a numeric value: {v}"

    @pytest.mark.parametrize(
        "model_file",
        [
            "qa_with_bing/flow.json",  # Old style
            "qa_with_bing",  # Old style folder
            "script_with_import/flow.dag.yaml",
            "script_with_import",
            "aggregation_complicated_example/flow.dag.yaml",
        ],
    )
    def test_basic_flow_exec_line(self, model_file, basic_executor: FlowExecutionCoodinator) -> None:
        model_file = MODEL_ROOT / model_file
        executor = self.resolve_flow_executor(model_file, basic_executor)
        model_and_variants_dir = model_file if model_file.is_dir() else model_file.parent
        samples = load_json(MODEL_ROOT / model_and_variants_dir / "inputs.json")
        if isinstance(samples, dict):
            samples = [samples]
        flow = executor._flow
        is_aggregation_flow = flow.has_aggregation_node()
        aggregation_inputs_list = {reference: [] for reference in executor._aggregation_inputs_references}
        inputs_list = {i: [] for i in flow.inputs}
        output_names = set(flow.outputs.keys())
        aggregation_outputs_names = {
            name
            for name, output in flow.outputs.items()
            if output.reference.value_type == InputValueType.NODE_REFERENCE
            and output.reference.value in executor.aggregation_nodes
        }
        for sample in samples:
            for k in inputs_list:
                assert k in sample, f"Input {k} not found in sample {sample}"
                inputs_list[k].append(sample[k])

            result = executor._exec(sample, None, 0)
            assert result.output is not None, f"Output not found in result {result}"
            assert result.node_run_infos is not None, f"Node run infos not found in result {result}"
            node_run_info_count = len(result.node_run_infos)
            node_count = len(flow.nodes) - len(executor.aggregation_nodes)
            err_msg = f"Node run info count {node_run_info_count} != node count {node_count}"
            assert node_run_info_count == node_count, err_msg
            for node_name, run_info in result.node_run_infos.items():
                node_in_flow = flow.get_node(node_name)
                assert node_in_flow is not None, f"Node {node_name} not found in flow {flow}"
                assert run_info.status == Status.Completed, f"Node {node_name} not succeeded: {run_info.status}"
                assert run_info.parent_run_id == result.run_info.run_id
            if not is_aggregation_flow:
                assert result.aggregation_inputs == {}, f"Got aggregation inputs which should be empty: {result}"
                continue

            aggr_inputs = result.aggregation_inputs
            assert isinstance(aggr_inputs, dict), f"Aggregation inputs not found: {result}"
            for reference in aggregation_inputs_list:
                assert reference in aggr_inputs, f"Aggregation input {reference} not found: {aggr_inputs}"
                aggregation_inputs_list[reference].append(aggr_inputs[reference])

            flow_results = result.output
            for name in output_names:
                if name in aggregation_outputs_names:
                    continue
                assert name in flow_results, f"Output {name} not found in result {flow_results}"
                assert flow_results[name] is not None, f"Output {name} is None in result {flow_results}"
        if not is_aggregation_flow:
            return

        # TODO: Remove the run_info logic to avoid the dependency on the run_tracker
        dummy_id = str(uuid.uuid4())
        run_info = executor._run_tracker.start_flow_run(
            flow_id=dummy_id, root_run_id=dummy_id, run_id=dummy_id, parent_run_id=dummy_id
        )
        aggr_results = executor.exec_aggregation(inputs_list, aggregation_inputs_list, run_info)
        metrics = aggr_results.metrics
        assert isinstance(metrics, dict) and len(metrics) > 0, f"Metrics not found: {metrics}"
        for k, v in metrics.items():
            assert isinstance(v, (int, float)), f"Metric {k} is not a numeric value: {v}"
        node_run_infos = aggr_results.node_run_infos
        for node in executor.aggregation_nodes:
            assert node in node_run_infos, f"Aggregation run info {node} not found: {node_run_infos}"
            assert node_run_infos[node].status == Status.Completed, f"Node {node} not succeeded: {node_run_infos[node]}"

    @pytest.mark.parametrize(
        "model_and_variants_dir",
        [
            "qa_with_bing",
        ],
    )
    def test_variant_flow_exec_line(self, model_and_variants_dir, basic_executor: FlowExecutionCoodinator) -> None:
        model_and_variants_dir = MODEL_ROOT / model_and_variants_dir
        flow_file = model_and_variants_dir / "flow.json"
        flow = Flow.deserialize(load_json(flow_file))
        variant_node = Node.deserialize(load_json(model_and_variants_dir / "variant_node.json"))
        assert variant_node.inputs["max_tokens"].value == "128"
        variant_tool = Tool.deserialize(load_json(model_and_variants_dir / "variant_tool.json"))
        assert variant_tool.name == "dummy_extract1"
        variant_tools = [variant_tool]
        flow.replace_with_variant(variant_node, variant_tools)
        assert flow.nodes[0].inputs["max_tokens"].value == "128"
        assert flow.tools[-1].name == "dummy_extract1"

        connections = {k: v for k, v in basic_executor._connections_in_env.items()}
        worker = basic_executor.create_flow_executor_by_model(flow_file, connections)
        output_names = list(flow.outputs.keys())
        samples = load_json(MODEL_ROOT / model_and_variants_dir / "inputs.json")
        for sample in samples:
            result = worker._exec(sample, None, 0)
            assert result.output is not None, f"Output not found in result {result}"
            assert result.aggregation_inputs is not None, f"Aggregation inputs not found in result {result}"

            flow_results = result.output
            for name in output_names:
                assert name in flow_results, f"Output {name} not found in result {flow_results}"
                assert flow_results[name] is not None, f"Output {name} is None in result {flow_results}"

    def test_ensure_flow_inputs_type(self, basic_executor: FlowExecutionCoodinator) -> None:
        model_file = "script_with_import/flow.dag.yaml"
        model_file = MODEL_ROOT / model_file
        executor = self.resolve_flow_executor(model_file, basic_executor)

        assert FlowValidator.ensure_flow_inputs_type(executor._flow, {"text": 1}) == {"text": "1"}
        assert FlowValidator.resolve_flow_inputs_type(executor._flow, {}) == {}
        with pytest.raises(InputNotFound):
            FlowValidator.ensure_flow_inputs_type(executor._flow, {})
