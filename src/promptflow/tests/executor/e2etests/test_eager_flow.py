import json
import os
from pathlib import Path
from tempfile import mkdtemp

import pytest

from promptflow._constants import OUTPUT_FILE_NAME
from promptflow._sdk.entities._run import Run
from promptflow._sdk.operations._local_storage_operations import LocalStorageOperations
from promptflow.batch._batch_engine import BatchEngine
from promptflow.batch._result import BatchResult
from promptflow.contracts.run_info import Status

from ..utils import (
    EAGER_FLOW_ROOT,
    RUNS_ROOT,
    get_bulk_inputs_from_jsonl,
    get_flow_folder,
    get_flow_inputs_file,
    get_yaml_file,
    load_jsonl,
)

SAMPLE_FLOW = "web_classification_no_variants"
SAMPLE_EVAL_FLOW = "classification_accuracy_evaluation"
SAMPLE_FLOW_WITH_PARTIAL_FAILURE = "python_tool_partial_failure"


class MockRun(object):
    def __init__(self, name: str, output_path: Path):
        self.name = name
        self._output_path = output_path
        self.data = None
        self._run_source = None
        self.flow = None


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
            (
                "callable_class_with_primitive",
                {"func_input": "${data.func_input}"},
                lambda x: x["output"] == "The object input is obj_input and the function input is func_input",
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
        "flow_folder, resume_from_run_name, inputs_mapping, init_kwargs",
        [
            (
                "basic_callable_class",
                "basic_callable_class_variant_0_20240423_154143_449844",
                {"func_input": "${data.func_input}"},
                {"obj_input": "obj_input"},
            ),
        ],
    )
    def test_batch_run_resume(self, flow_folder, resume_from_run_name, inputs_mapping, init_kwargs):
        run_storage = LocalStorageOperations(Run(flow=flow_folder))
        batch_engine = BatchEngine(
            get_yaml_file(flow_folder, root=EAGER_FLOW_ROOT),
            get_flow_folder(flow_folder, root=EAGER_FLOW_ROOT),
            init_kwargs=init_kwargs,
            storage=run_storage,
        )
        input_dirs = {"data": get_flow_inputs_file(flow_folder, root=EAGER_FLOW_ROOT)}
        output_dir = Path(mkdtemp())

        run_folder = RUNS_ROOT / resume_from_run_name
        mock_resume_from_run = MockRun(resume_from_run_name, run_folder)
        resume_from_run_storage = LocalStorageOperations(mock_resume_from_run)
        resume_from_run_output_dir = resume_from_run_storage.outputs_folder
        resume_run_id = mock_resume_from_run.name + "_resume"
        resume_run_batch_results = batch_engine.run(
            input_dirs,
            inputs_mapping,
            output_dir,
            resume_run_id,
            resume_from_run_storage=resume_from_run_storage,
            resume_from_run_output_dir=resume_from_run_output_dir,
        )
        assert resume_run_batch_results.status == Status.Completed
        output_path = os.path.join(resume_from_run_output_dir, "output.jsonl")
        with open(output_path, "r") as file:
            original_output = [json.loads(line) for line in file]
        original_completed_count = len(original_output)
        resume_completed_count = resume_run_batch_results.completed_lines
        assert original_completed_count < resume_completed_count

    def test_batch_run_with_callable_entry(self):
        flow_folder = "basic_callable_class"
        batch_engine = BatchEngine(MyFlow("obj_input"), get_flow_folder(flow_folder, root=EAGER_FLOW_ROOT))
        input_dirs = {"data": get_flow_inputs_file(flow_folder, root=EAGER_FLOW_ROOT)}
        output_dir = Path(mkdtemp())
        batch_result = batch_engine.run(input_dirs, {"func_input": "${data.func_input}"}, output_dir)
        validate_batch_result(
            batch_result,
            flow_folder,
            output_dir,
            lambda x: x["obj_input"] == "obj_input" and x["func_input"] == "func_input",
        )
        assert batch_result.metrics == {"length": 4}


# Used for testing callable entry
class MyFlow:
    def __init__(self, obj_input: str):
        self.obj_input = obj_input

    def __call__(self, func_input: str) -> dict:
        return {
            "obj_input": self.obj_input,
            "func_input": func_input,
            "obj_id": id(self),
        }

    def __aggregate__(self, results: list) -> dict:
        return {"length": len(results)}
