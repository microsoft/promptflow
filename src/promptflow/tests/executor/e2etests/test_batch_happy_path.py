import uuid
from pathlib import Path
from tempfile import mkdtemp

import pytest

from promptflow._utils.dataclass_serializer import serialize
from promptflow.batch import BatchEngine
from promptflow.batch._batch_inputs_processor import BatchInputsProcessor
from promptflow.contracts.run_info import FlowRunInfo
from promptflow.contracts.run_info import RunInfo as NodeRunInfo
from promptflow.contracts.run_info import Status
from promptflow.executor import FlowExecutor
from promptflow.executor.flow_executor import BatchResult, LineResult
from promptflow.storage import AbstractRunStorage

from ..utils import (
    get_flow_expected_metrics,
    get_flow_expected_status_summary,
    get_flow_folder,
    get_flow_inputs_file,
    get_flow_sample_inputs,
    get_yaml_file,
)

SAMPLE_FLOW = "web_classification_no_variants"
SAMPLE_EVAL_FLOW = "classification_accuracy_evaluation"
SAMPLE_FLOW_WITH_PARTIAL_FAILURE = "python_tool_partial_failure"


class MemoryRunStorage(AbstractRunStorage):
    def __init__(self):
        self._node_runs = {}
        self._flow_runs = {}

    def persist_flow_run(self, run_info: FlowRunInfo):
        run_info.result = None
        self._flow_runs[run_info.run_id] = run_info

    def persist_node_run(self, run_info: NodeRunInfo):
        run_info.result = None
        self._node_runs[run_info.run_id] = run_info


def submit_batch_run(
    flow_folder, inputs_mapping, *, input_file_name="samples.json", run_id=None, connections={}, storage=None
):
    batch_engine = BatchEngine(
        get_yaml_file(flow_folder), get_flow_folder(flow_folder), connections=connections, storage=storage
    )
    input_dirs = {}
    if inputs_mapping:
        input_dirs = {"data": get_flow_inputs_file(flow_folder, file_name=input_file_name)}
    output_dir = Path(mkdtemp())
    return batch_engine.run(input_dirs, inputs_mapping, output_dir, run_id=run_id)


def get_batch_inputs_line(flow_folder, sample_inputs_file="samples.json"):
    inputs = get_flow_sample_inputs(flow_folder, sample_inputs_file=sample_inputs_file)
    return len(inputs)


@pytest.mark.usefixtures("use_secrets_config_file", "dev_connections")
@pytest.mark.e2etest
class TestBatch:
    def test_batch_storage(self, dev_connections):
        mem_run_storage = MemoryRunStorage()
        run_id = str(uuid.uuid4())
        inputs_mapping = {
            "line_number": "${data.line_number}",
            "variant_id": "${data.variant_id}",
            "groundtruth": "${data.groundtruth}",
            "prediction": "${data.prediction}",
        }
        batch_result = submit_batch_run(
            SAMPLE_FLOW, inputs_mapping, run_id=run_id, connections=dev_connections, storage=mem_run_storage
        )

        nlines = get_batch_inputs_line(SAMPLE_FLOW)
        msg = f"Only {len(batch_result.line_results)}/{nlines} lines are returned."
        assert len(batch_result.line_results) == nlines, msg
        for line_result in batch_result.line_results:
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
        "flow_folder, inputs_mapping",
        [
            (
                SAMPLE_FLOW,
                {
                    "line_number": "${data.line_number}",
                    "variant_id": "${data.variant_id}",
                    "groundtruth": "${data.groundtruth}",
                    "prediction": "${data.prediction}",
                },
            ),
            (
                "prompt_tools",
                {"text": "${data.text}"},
            ),
            (
                "script_with___file__",
                {"text": "${data.text}"},
            ),
            ("connection_as_input", {}),
            ("sample_flow_with_functions", {}),
        ],
    )
    def test_batch_run(self, flow_folder, inputs_mapping, dev_connections):
        batch_result = submit_batch_run(flow_folder, inputs_mapping, connections=dev_connections)
        assert isinstance(batch_result, BatchResult)
        nlines = get_batch_inputs_line(flow_folder)
        msg = f"Bulk result only has {len(batch_result.line_results)}/{nlines} outputs"
        assert len(batch_result.outputs) == nlines, msg
        for i, output in enumerate(batch_result.outputs):
            assert isinstance(output, dict)
            assert "line_number" in output, f"line_number is not in {i}th output {output}"
            assert output["line_number"] == i, f"line_number is not correct in {i}th output {output}"
        msg = f"Bulk result only has {len(batch_result.line_results)}/{nlines} line results"
        assert len(batch_result.outputs) == nlines, msg
        for i, line_result in enumerate(batch_result.line_results):
            assert isinstance(line_result, LineResult)
            assert line_result.run_info.status == Status.Completed, f"{i}th line got {line_result.run_info.status}"

    def test_batch_run_then_eval(self, dev_connections):
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
        batch_inputs_processor = BatchInputsProcessor(eval_executor._working_dir, eval_executor._flow.inputs)
        mapped_inputs = batch_inputs_processor._validate_and_apply_inputs_mapping(input_dicts, inputs_mapping)
        result = eval_executor.exec_bulk(mapped_inputs)
        assert len(result.outputs) == nlines, f"Only {len(result.outputs)}/{nlines} outputs are returned."
        assert len(result.metrics) > 0, "No metrics are returned."
        assert result.metrics["accuracy"] == 0, f"Accuracy should be 0, got {result.metrics}."

    def test_batch_with_metrics(self, dev_connections):
        flow_folder = SAMPLE_EVAL_FLOW
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections, raise_ex=True)
        run_id = str(uuid.uuid4())
        bulk_inputs = self.get_bulk_inputs(flow_folder=flow_folder)
        bulk_results = executor.exec_bulk(bulk_inputs, run_id)
        assert isinstance(bulk_results, BatchResult)
        assert isinstance(bulk_results.metrics, dict)
        assert bulk_results.metrics == get_flow_expected_metrics(flow_folder)
        status_summary = bulk_results.get_status_summary()
        assert status_summary == get_flow_expected_status_summary(flow_folder)

    def test_batch_with_partial_failure(self, dev_connections):
        flow_folder = SAMPLE_FLOW_WITH_PARTIAL_FAILURE
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections, raise_ex=False)
        run_id = str(uuid.uuid4())
        bulk_inputs = self.get_bulk_inputs(flow_folder=flow_folder)
        bulk_results = executor.exec_bulk(bulk_inputs, run_id)
        assert isinstance(bulk_results, BatchResult)
        status_summary = bulk_results.get_status_summary()
        assert status_summary == get_flow_expected_status_summary(flow_folder)

    def test_batch_with_line_number(self, dev_connections):
        flow_folder = SAMPLE_FLOW_WITH_PARTIAL_FAILURE
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections, raise_ex=False)
        run_id = str(uuid.uuid4())
        bulk_inputs = self.get_bulk_inputs(flow_folder=flow_folder, sample_inputs_file="inputs.json", return_dict=True)
        bulk_inputs_mapping = self.get_bulk_inputs(
            flow_folder=flow_folder, sample_inputs_file="inputs_mapping.json", return_dict=True
        )
        batch_inputs_processor = BatchInputsProcessor(executor._working_dir, executor._flow.inputs)
        resolved_inputs = batch_inputs_processor._validate_and_apply_inputs_mapping(bulk_inputs, bulk_inputs_mapping)
        bulk_results = executor.exec_bulk(resolved_inputs, run_id)
        assert isinstance(bulk_results, BatchResult)
        assert len(bulk_results.outputs) == 2
        assert bulk_results.outputs == [
            {"line_number": 0, "output": 1},
            {"line_number": 6, "output": 7},
        ]

    # TODO: Add test for flow with langchain traces
    def test_batch_with_openai_metrics(self, dev_connections):
        classification_executor = FlowExecutor.create(get_yaml_file(SAMPLE_FLOW), dev_connections, raise_ex=True)
        bulk_inputs = self.get_bulk_inputs()
        bulk_results = classification_executor.exec_bulk(bulk_inputs)
        assert len(bulk_results.outputs) == len(bulk_inputs)
        openai_metrics = bulk_results.get_openai_metrics()
        assert "total_tokens" in openai_metrics
        assert openai_metrics["total_tokens"] > 0

    def test_batch_with_default_input(self):
        # Assert for single node run.
        default_input_value = "input value from default"
        yaml_file = get_yaml_file("default_input")
        executor = FlowExecutor.create(yaml_file, {})

        # Assert for bulk run.
        bulk_result = executor.exec_bulk([{}])
        assert bulk_result.line_results[0].run_info.status == Status.Completed
        assert bulk_result.line_results[0].output["output"] == default_input_value
        bulk_aggregate_node = bulk_result.aggr_results.node_run_infos["aggregate_node"]
        assert bulk_aggregate_node.status == Status.Completed
        assert bulk_aggregate_node.output == [default_input_value]

    @pytest.mark.parametrize(
        "flow_folder, batch_input, expected_type, validate_inputs",
        [
            ("simple_aggregation", [{"text": 4}], str, True),
            ("simple_aggregation", [{"text": 4.5}], str, True),
            ("simple_aggregation", [{"text": "3.0"}], str, True),
            ("simple_aggregation", [{"text": 4}], int, False),
        ],
    )
    def test_batch_run_line_result(self, flow_folder, batch_input, expected_type, validate_inputs, dev_connections):
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)
        bulk_result = executor.exec_bulk(
            batch_input,
            validate_inputs=validate_inputs,
        )
        assert type(bulk_result.line_results[0].run_info.inputs["text"]) is expected_type
