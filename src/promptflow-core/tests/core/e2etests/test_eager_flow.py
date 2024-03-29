from dataclasses import is_dataclass

import pytest

from promptflow.contracts.run_info import Status
from promptflow.executor._errors import FlowEntryInitializationError
from promptflow.executor._result import LineResult
from promptflow.executor._script_executor import ScriptExecutor
from promptflow.executor.flow_executor import FlowExecutor

from ...utils import EAGER_FLOW_ROOT, get_yaml_file

SAMPLE_FLOW = "web_classification_no_variants"
SAMPLE_EVAL_FLOW = "classification_accuracy_evaluation"
SAMPLE_FLOW_WITH_PARTIAL_FAILURE = "python_tool_partial_failure"


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

    def test_flow_with_operation_context(self):
        flow_folder = "flow_with_operation_context"
        flow_file = get_yaml_file(flow_folder, root=EAGER_FLOW_ROOT)
        executor = FlowExecutor.create(flow_file=flow_file, connections={})
        line_result = executor.exec_line(inputs={}, index=0)

        assert isinstance(line_result, LineResult)
        assert line_result.run_info.status == Status.Completed
        assert line_result.output["flow-id"] == line_result.run_info.flow_id
        assert line_result.output["root-run-id"] == line_result.run_info.root_run_id

    def test_execute_init_func_with_user_error(self):
        flow_folder = "callable_flow_with_init_exception"
        flow_file = get_yaml_file(flow_folder, root=EAGER_FLOW_ROOT)
        with pytest.raises(FlowEntryInitializationError) as e:
            ScriptExecutor(flow_file=flow_file, init_kwargs={})
        assert "Failed to initialize flow entry with" in str(e.value)
