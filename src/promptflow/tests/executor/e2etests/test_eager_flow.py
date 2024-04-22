import asyncio
from pathlib import Path
from tempfile import mkdtemp
from types import AsyncGeneratorType

import pytest

from promptflow._constants import OUTPUT_FILE_NAME
from promptflow.batch._batch_engine import BatchEngine
from promptflow.batch._result import BatchResult
from promptflow.executor._script_executor import ScriptExecutor

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


async def get_next_async(generator):
    return await generator.__anext__()


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

    @pytest.mark.parametrize("allow_generator_output", [False, True])
    def test_trace_behavior_with_async_generator_output(self, allow_generator_output):
        """Test to verify the trace output list behavior for a flex flow with an async generator output."""

        flow_file = get_yaml_file("async_stream_output", root=EAGER_FLOW_ROOT)

        # Submitting eager flow to script executor
        executor = ScriptExecutor(flow_file=flow_file)
        result = executor.exec_line(inputs={}, allow_generator_output=allow_generator_output)

        # Check the status of the run
        assert (
            result.run_info.status.value == "Completed"
        ), f"Expected status to be 'Completed', but got {result.run_info.status.value}"

        # Check the number and content of api calls
        api_calls = result.run_info.api_calls
        assert len(api_calls) == 1, f"Expected one api call, but got {len(api_calls)}"
        assert "output" in api_calls[0], "The 'output' key was not found in the API calls"
        generator_output_trace = api_calls[0]["output"]
        assert isinstance(generator_output_trace, list), "Expected generator_output_trace to be a list"

        if allow_generator_output:
            # If generator output is allowed, the trace list should be empty before consumption
            assert not generator_output_trace, "Expected generator_output_trace to be empty"
            assert isinstance(result.output, AsyncGeneratorType), "Expected result.output to be an async generator"
            # Consume the generator and check that it yields text
            try:
                generated_text = asyncio.run(get_next_async(result.output))
                assert isinstance(generated_text, str)
                # Verify the trace list contains the most recently generated item
                assert generator_output_trace[-1] == generated_text
            except StopIteration:
                assert False, "Async generator did not generate any text"
        else:
            # If generator output is not allowed, the trace list should contain generated items
            assert generator_output_trace, "Expected generator_output_trace to contain generated items"
            assert all(
                isinstance(item, str) for item in generator_output_trace
            ), "Expected all items in generator_output_trace to be strings"
