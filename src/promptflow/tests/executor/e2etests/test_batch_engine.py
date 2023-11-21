import uuid
from pathlib import Path
from tempfile import mkdtemp

import pytest

from promptflow._utils.utils import dump_list_to_jsonl
from promptflow.batch._batch_engine import OUTPUT_FILE_NAME, BatchEngine
from promptflow.batch._errors import EmptyInputsData
from promptflow.batch._result import BatchResult
from promptflow.contracts.run_info import Status
from promptflow.executor._errors import InputNotFound

from ..utils import (
    MemoryRunStorage,
    get_flow_expected_metrics,
    get_flow_expected_status_summary,
    get_flow_folder,
    get_flow_inputs_file,
    get_flow_sample_inputs,
    get_yaml_file,
    load_jsonl,
)

SAMPLE_FLOW = "web_classification_no_variants"
SAMPLE_EVAL_FLOW = "classification_accuracy_evaluation"
SAMPLE_FLOW_WITH_PARTIAL_FAILURE = "python_tool_partial_failure"


def submit_batch_run(
    flow_folder,
    inputs_mapping,
    *,
    input_dirs={},
    input_file_name="samples.json",
    run_id=None,
    connections={},
    storage=None,
    return_output_dir=False,
):
    batch_engine = BatchEngine(
        get_yaml_file(flow_folder), get_flow_folder(flow_folder), connections=connections, storage=storage
    )
    if not input_dirs and inputs_mapping:
        input_dirs = {"data": get_flow_inputs_file(flow_folder, file_name=input_file_name)}
    output_dir = Path(mkdtemp())
    if return_output_dir:
        return batch_engine.run(input_dirs, inputs_mapping, output_dir, run_id=run_id), output_dir
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
        inputs_mapping = {"url": "${data.url}"}
        batch_result = submit_batch_run(
            SAMPLE_FLOW, inputs_mapping, run_id=run_id, connections=dev_connections, storage=mem_run_storage
        )

        nlines = get_batch_inputs_line(SAMPLE_FLOW)
        assert batch_result.total_lines == nlines
        assert batch_result.completed_lines == nlines
        assert len(mem_run_storage._flow_runs) == nlines
        assert all(flow_run_info.status == Status.Completed for flow_run_info in mem_run_storage._flow_runs.values())
        assert all(node_run_info.status == Status.Completed for node_run_info in mem_run_storage._node_runs.values())

    @pytest.mark.parametrize(
        "flow_folder, inputs_mapping",
        [
            (
                SAMPLE_FLOW,
                {"url": "${data.url}"},
            ),
            (
                "prompt_tools",
                {"text": "${data.text}"},
            ),
            (
                "script_with___file__",
                {"text": "${data.text}"},
            ),
            (
                "sample_flow_with_functions",
                {"question": "${data.question}"},
            ),
        ],
    )
    def test_batch_run(self, flow_folder, inputs_mapping, dev_connections):
        batch_result, output_dir = submit_batch_run(
            flow_folder, inputs_mapping, connections=dev_connections, return_output_dir=True
        )

        assert isinstance(batch_result, BatchResult)
        nlines = get_batch_inputs_line(flow_folder)
        assert batch_result.total_lines == nlines
        assert batch_result.completed_lines == nlines
        assert batch_result.start_time < batch_result.end_time
        assert batch_result.system_metrics.duration > 0

        outputs = load_jsonl(output_dir / OUTPUT_FILE_NAME)
        assert len(outputs) == nlines
        for i, output in enumerate(outputs):
            assert isinstance(output, dict)
            assert "line_number" in output, f"line_number is not in {i}th output {output}"
            assert output["line_number"] == i, f"line_number is not correct in {i}th output {output}"

    def test_batch_run_then_eval(self, dev_connections):
        batch_resutls, output_dir = submit_batch_run(
            SAMPLE_FLOW, {"url": "${data.url}"}, connections=dev_connections, return_output_dir=True
        )
        nlines = get_batch_inputs_line(SAMPLE_FLOW)
        assert batch_resutls.completed_lines == nlines

        input_dirs = {"data": get_flow_inputs_file(SAMPLE_FLOW, file_name="samples.json"), "run.outputs": output_dir}
        inputs_mapping = {
            "variant_id": "baseline",
            "groundtruth": "${data.url}",
            "prediction": "${run.outputs.category}",
        }
        eval_result = submit_batch_run(SAMPLE_EVAL_FLOW, inputs_mapping, input_dirs=input_dirs)
        assert eval_result.completed_lines == nlines, f"Only returned {eval_result.completed_lines}/{nlines} outputs."
        assert len(eval_result.metrics) > 0, "No metrics are returned."
        assert eval_result.metrics["accuracy"] == 0, f"Accuracy should be 0, got {eval_result.metrics}."

    def test_batch_with_metrics(self, dev_connections):
        flow_folder = SAMPLE_EVAL_FLOW
        inputs_mapping = {
            "variant_id": "${data.variant_id}",
            "groundtruth": "${data.groundtruth}",
            "prediction": "${data.prediction}",
        }
        batch_results = submit_batch_run(flow_folder, inputs_mapping, connections=dev_connections)
        assert isinstance(batch_results, BatchResult)
        assert isinstance(batch_results.metrics, dict)
        assert batch_results.metrics == get_flow_expected_metrics(flow_folder)
        assert batch_results.total_lines == batch_results.completed_lines
        assert batch_results.node_status == get_flow_expected_status_summary(flow_folder)

    def test_batch_with_partial_failure(self, dev_connections):
        flow_folder = SAMPLE_FLOW_WITH_PARTIAL_FAILURE
        inputs_mapping = {"idx": "${data.idx}", "mod": "${data.mod}", "mod_2": "${data.mod_2}"}
        batch_results = submit_batch_run(flow_folder, inputs_mapping, connections=dev_connections)
        assert isinstance(batch_results, BatchResult)
        assert batch_results.total_lines == 10
        assert batch_results.completed_lines == 5
        assert batch_results.failed_lines == 5
        assert batch_results.node_status == get_flow_expected_status_summary(flow_folder)

    def test_batch_with_line_number(self, dev_connections):
        flow_folder = SAMPLE_FLOW_WITH_PARTIAL_FAILURE
        input_dirs = {"data": "inputs/data.jsonl", "output": "inputs/output.jsonl"}
        inputs_mapping = {"idx": "${output.idx}", "mod": "${data.mod}", "mod_2": "${data.mod_2}"}
        batch_results, output_dir = submit_batch_run(
            flow_folder, inputs_mapping, input_dirs=input_dirs, connections=dev_connections, return_output_dir=True
        )
        assert isinstance(batch_results, BatchResult)
        outputs = load_jsonl(output_dir / OUTPUT_FILE_NAME)
        assert len(outputs) == 2
        assert outputs == [
            {"line_number": 0, "output": 1},
            {"line_number": 6, "output": 7},
        ]

    def test_batch_with_openai_metrics(self, dev_connections):
        inputs_mapping = {"url": "${data.url}"}
        batch_result, output_dir = submit_batch_run(
            SAMPLE_FLOW, inputs_mapping, connections=dev_connections, return_output_dir=True
        )
        nlines = get_batch_inputs_line(SAMPLE_FLOW)
        outputs = load_jsonl(output_dir / OUTPUT_FILE_NAME)
        assert len(outputs) == nlines
        assert batch_result.system_metrics.total_tokens > 0
        assert batch_result.system_metrics.prompt_tokens > 0
        assert batch_result.system_metrics.completion_tokens > 0

    def test_batch_with_default_input(self):
        mem_run_storage = MemoryRunStorage()
        default_input_value = "input value from default"
        inputs_mapping = {"text": "${data.text}"}
        batch_result, output_dir = submit_batch_run(
            "default_input", inputs_mapping, storage=mem_run_storage, return_output_dir=True
        )
        assert batch_result.total_lines == batch_result.completed_lines

        outputs = load_jsonl(output_dir / OUTPUT_FILE_NAME)
        assert len(outputs) == 1
        assert outputs[0]["output"] == default_input_value
        assert all(
            node_run_info.status == Status.Completed and node_run_info.output == [default_input_value]
            for node_run_info in mem_run_storage._node_runs.values()
            if node_run_info.node == "aggregate_node"
        )

    @pytest.mark.parametrize(
        "flow_folder, batch_input, expected_type",
        [
            ("simple_aggregation", [{"text": 4}], str),
            ("simple_aggregation", [{"text": 4.5}], str),
            ("simple_aggregation", [{"text": "3.0"}], str),
        ],
    )
    def test_batch_run_line_result(self, flow_folder, batch_input, expected_type):
        mem_run_storage = MemoryRunStorage()
        input_file = Path(mkdtemp()) / "inputs.jsonl"
        dump_list_to_jsonl(input_file, batch_input)
        input_dirs = {"data": input_file}
        inputs_mapping = {"text": "${data.text}"}
        batch_results = submit_batch_run(flow_folder, inputs_mapping, input_dirs=input_dirs, storage=mem_run_storage)
        assert isinstance(batch_results, BatchResult)
        assert all(
            type(flow_run_info.inputs["text"]) is expected_type for flow_run_info in mem_run_storage._flow_runs.values()
        )

    @pytest.mark.parametrize(
        "flow_folder, input_mapping, error_class, error_message",
        [
            (
                "connection_as_input",
                {},
                InputNotFound,
                "The input for flow cannot be empty in batch mode. Please review your flow and provide valid inputs.",
            ),
            (
                "script_with___file__",
                {"text": "${data.text}"},
                EmptyInputsData,
                "Couldn't find any inputs data at the given input paths. Please review the provided path "
                "and consider resubmitting.",
            ),
        ],
    )
    def test_batch_run_failure(self, flow_folder, input_mapping, error_class, error_message):
        with pytest.raises(error_class) as e:
            submit_batch_run(flow_folder, input_mapping, input_file_name="empty_inputs.jsonl")
        assert error_message in e.value.message
