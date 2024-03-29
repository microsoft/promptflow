from dataclasses import is_dataclass
from pathlib import Path
from tempfile import mkdtemp

import pytest

from promptflow._constants import OUTPUT_FILE_NAME
from promptflow._core.tool_meta_generator import PythonLoadError
from promptflow.batch._batch_engine import BatchEngine
from promptflow.batch._result import BatchResult, LineResult
from promptflow.contracts.run_info import Status
from promptflow.executor._errors import FlowEntryInitializationError
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
        "flow_folder, inputs, ensure_output, init_kwargs",
        [
            ("dummy_flow_with_trace", {"text": "text", "models": ["model"]}, lambda x: x == "dummy_output", None),
            (
                "flow_with_dataclass_output",
                {"text": "text", "models": ["model"]},
                lambda x: is_dataclass(x) and x.text == "text" and x.models == ["model"],
                None,
            ),
            (
                "basic_callable_class",
                {"func_input": "func_input"},
                lambda x: x["func_input"] == "func_input",
                {"obj_input": "obj_input"},
            ),
        ],
    )
    def test_flow_run(self, flow_folder, inputs, ensure_output, init_kwargs):
        flow_file = get_yaml_file(flow_folder, root=EAGER_FLOW_ROOT)

        # Test submitting eager flow to script executor
        executor = ScriptExecutor(flow_file=flow_file, init_kwargs=init_kwargs)
        line_result = executor.exec_line(inputs=inputs, index=0)
        assert isinstance(line_result, LineResult)
        assert ensure_output(line_result.output)

        # Test submitting eager flow to flow executor
        executor = FlowExecutor.create(flow_file=flow_file, connections={}, init_kwargs=init_kwargs)
        line_result1 = executor.exec_line(inputs=inputs, index=0)
        assert isinstance(line_result1, LineResult)
        assert ensure_output(line_result1.output)

        # run the same line again will get same output
        line_result2 = executor.exec_line(inputs=inputs, index=0)
        assert line_result1.output == line_result2.output

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
        "flow_folder, inputs_mapping, ensure_output, init_kwargs",
        [
            (
                "dummy_flow_with_trace",
                {"text": "${data.text}", "models": "${data.models}"},
                lambda x: "output" in x and x["output"] == "dummy_output",
                None,
            ),
            (
                "flow_with_dataclass_output",
                {"text": "${data.text}", "models": "${data.models}"},
                lambda x: x["text"] == "text" and isinstance(x["models"], list),
                None,
            ),
            (
                "basic_callable_class",
                {"func_input": "${data.func_input}"},
                lambda x: x["obj_input"] == "obj_input" and x["func_input"] == "func_input",
                {"obj_input": "obj_input"},
            ),
        ],
    )
    def test_batch_run(self, flow_folder, inputs_mapping, ensure_output, init_kwargs):
        batch_engine = BatchEngine(
            get_yaml_file(flow_folder, root=EAGER_FLOW_ROOT),
            get_flow_folder(flow_folder, root=EAGER_FLOW_ROOT),
            init_kwargs=init_kwargs,
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
        assert line_result.run_info.status == Status.Completed
        assert line_result.output["flow-id"] == line_result.run_info.flow_id
        assert line_result.output["root-run-id"] == line_result.run_info.root_run_id

    @pytest.mark.parametrize(
        "worker_count, ensure_output",
        [
            # batch run with 1 worker
            # obj id in each line run should be the same
            (
                1,
                lambda outputs: len(outputs) == 4 and outputs[0]["obj_id"] == outputs[1]["obj_id"],
            ),
            # batch run with 2 workers
            (
                2,
                # there will be at most 2 instances be created.
                lambda outputs: len(outputs) == 4 and len(set([o["obj_id"] for o in outputs])) <= 2,
            ),
        ],
    )
    def test_batch_run_with_init_multiple_workers(self, worker_count, ensure_output):
        flow_folder = "basic_callable_class"
        init_kwargs = {"obj_input": "obj_input"}

        input_dirs = {"data": get_flow_inputs_file(flow_folder, root=EAGER_FLOW_ROOT)}
        output_dir = Path(mkdtemp())

        batch_engine = BatchEngine(
            get_yaml_file(flow_folder, root=EAGER_FLOW_ROOT),
            get_flow_folder(flow_folder, root=EAGER_FLOW_ROOT),
            init_kwargs=init_kwargs,
            worker_count=worker_count,
        )

        batch_engine.run(input_dirs, {"func_input": "${data.func_input}"}, output_dir)
        outputs = load_jsonl(output_dir / OUTPUT_FILE_NAME)
        assert ensure_output(outputs), outputs

    @pytest.mark.parametrize(
        "flow_folder, expected_exception, expected_error_msg",
        [
            ("callable_flow_with_init_exception", FlowEntryInitializationError, "Failed to initialize flow entry with"),
            ("invalid_illegal_entry", PythonLoadError, "Failed to load python module for"),
            ("incorrect_entry", PythonLoadError, "Failed to load python module for"),
        ],
    )
    def test_execute_func_with_user_error(self, flow_folder, expected_exception, expected_error_msg):
        flow_file = get_yaml_file(flow_folder, root=EAGER_FLOW_ROOT)
        with pytest.raises(expected_exception) as e:
            ScriptExecutor(flow_file=flow_file)
        assert expected_error_msg in str(e.value)
