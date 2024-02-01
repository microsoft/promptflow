from dataclasses import is_dataclass
from pathlib import Path
from tempfile import mkdtemp

import pytest

from promptflow.batch._batch_engine import OUTPUT_FILE_NAME, BatchEngine
from promptflow.batch._result import BatchResult, LineResult
from promptflow.contracts.run_info import Status
from promptflow.executor._script_executor import ScriptExecutor
from promptflow.executor.flow_executor import FlowExecutor

from ..utils import (
    EAGER_FLOW_ROOT,
    get_bulk_inputs_from_jsonl,
    get_flow_folder,
    get_flow_inputs_file,
    get_yaml_file,
    load_jsonl,
)

SAMPLE_FLOW = "web_classification_no_variants"
SAMPLE_EVAL_FLOW = "classification_accuracy_evaluation"
SAMPLE_FLOW_WITH_PARTIAL_FAILURE = "python_tool_partial_failure"


def validate_batch_result(batch_result: BatchResult, flow_folder, output_dir, ensure_output):
    assert isinstance(batch_result, BatchResult)
    nlines = len(get_bulk_inputs_from_jsonl(flow_folder, root=EAGER_FLOW_ROOT))
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
        assert ensure_output(output)


@pytest.mark.usefixtures("dev_connections")
@pytest.mark.e2etest
class TestEagerFlow:
    @pytest.mark.parametrize(
        "flow_folder, inputs, ensure_output",
        [
            ("dummy_flow_with_trace", {"text": "text", "models": ["model"]}, lambda x: x == "dummy_output"),
            (
                "flow_with_dataclass_output",
                {"text": "text", "models": ["model"]},
                lambda x: is_dataclass(x) and x.text == "text" and x.models == ["model"],
            ),
        ],
    )
    def test_flow_run(self, flow_folder, inputs, ensure_output):
        flow_file = get_yaml_file(flow_folder, root=EAGER_FLOW_ROOT)

        # Test submitting eager flow to script executor
        executor = ScriptExecutor(flow_file=flow_file)
        line_result = executor.exec_line(inputs=inputs, index=0)
        assert isinstance(line_result, LineResult)
        assert ensure_output(line_result.output)

        # Test submitting eager flow to flow executor
        executor = FlowExecutor.create(flow_file=flow_file, connections={})
        line_result = executor.exec_line(inputs=inputs, index=0)
        assert isinstance(line_result, LineResult)
        assert ensure_output(line_result.output)

    def test_flow_run_with_invalid_case(self):
        flow_folder = "dummy_flow_with_exception"
        flow_file = get_yaml_file(flow_folder, root=EAGER_FLOW_ROOT)
        executor = ScriptExecutor(flow_file=flow_file)
        line_result = executor.exec_line(inputs={"text": "text"}, index=0)

        assert isinstance(line_result, LineResult)
        assert line_result.output is None
        assert line_result.run_info.status == Status.Failed
        assert "dummy exception" in line_result.run_info.error["message"]

    @pytest.mark.parametrize(
        "flow_folder, inputs_mapping, ensure_output",
        [
            (
                "dummy_flow_with_trace",
                {"text": "${data.text}", "models": "${data.models}"},
                lambda x: "output" in x and x["output"] == "dummy_output",
            ),
            (
                "flow_with_dataclass_output",
                {"text": "${data.text}", "models": "${data.models}"},
                lambda x: x["text"] == "text" and isinstance(x["models"], list),
            ),
        ],
    )
    def test_batch_run(self, flow_folder, inputs_mapping, ensure_output):
        batch_engine = BatchEngine(
            get_yaml_file(flow_folder, root=EAGER_FLOW_ROOT),
            get_flow_folder(flow_folder, root=EAGER_FLOW_ROOT),
        )
        input_dirs = {"data": get_flow_inputs_file(flow_folder, root=EAGER_FLOW_ROOT)}
        output_dir = Path(mkdtemp())
        batch_result = batch_engine.run(input_dirs, inputs_mapping, output_dir)
        validate_batch_result(batch_result, flow_folder, output_dir, ensure_output)

    def test_batch_run_with_invalid_case(self):
        flow_folder = "dummy_flow_with_exception"
        batch_engine = BatchEngine(
            get_yaml_file(flow_folder, root=EAGER_FLOW_ROOT),
            get_flow_folder(flow_folder, root=EAGER_FLOW_ROOT),
        )
        input_dirs = {"data": get_flow_inputs_file(flow_folder, root=EAGER_FLOW_ROOT)}
        output_dir = Path(mkdtemp())
        batch_result = batch_engine.run(input_dirs, {"text": "${data.text}"}, output_dir)

        assert isinstance(batch_result, BatchResult)
        nlines = len(get_bulk_inputs_from_jsonl(flow_folder, root=EAGER_FLOW_ROOT))
        assert batch_result.total_lines == nlines
        assert batch_result.failed_lines == nlines
        assert batch_result.start_time < batch_result.end_time
        assert batch_result.system_metrics.duration > 0

    def test_flow_with_operation_context(self):
        flow_folder = "flow_with_operation_context"
        flow_file = get_yaml_file(flow_folder, root=EAGER_FLOW_ROOT)
        executor = FlowExecutor.create(flow_file=flow_file, connections={})
        line_result = executor.exec_line(inputs={}, index=0)

        assert isinstance(line_result, LineResult)
        assert line_result.output["flow-id"] == line_result.run_info.flow_id
        assert line_result.output["root-run-id"] == line_result.run_info.root_run_id
