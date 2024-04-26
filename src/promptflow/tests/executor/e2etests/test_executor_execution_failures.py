import re
import sys

import pytest

from promptflow._core._errors import ToolExecutionError
from promptflow.contracts.run_info import Status
from promptflow.executor import FlowExecutor

from ..utils import get_yaml_file

SAMPLE_FLOW = "web_classification_no_variants"
SAMPLE_EVAL_FLOW = "classification_accuracy_evaluation"
SAMPLE_FLOW_WITH_PARTIAL_FAILURE = "python_tool_partial_failure"
SAMPLE_FLOW_WITH_LANGCHAIN_TRACES = "flow_with_langchain_traces"

expected_stack_traces = {
    "sync_tools_failures": """Traceback (most recent call last):
sync_fail.py", line 11, in raise_an_exception
    raise_exception(s)
sync_fail.py", line 5, in raise_exception
    raise Exception(msg)
Exception: In raise_exception: dummy_input

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
in wrapped
    output = func(*args, **kwargs)
             ^^^^^^^^^^^^^^^^^^^^^
sync_fail.py", line 13, in raise_an_exception
    raise Exception(f"In tool raise_an_exception: {s}") from e
Exception: In tool raise_an_exception: dummy_input
""".split(
        "\n"
    ),
    "async_tools_failures": """Traceback (most recent call last):
async_fail.py", line 11, in raise_an_exception_async
    await raise_exception_async(s)
async_fail.py", line 5, in raise_exception_async
    raise Exception(msg)
Exception: In raise_exception_async: dummy_input

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
in wrapped
    output = await func(*args, **kwargs)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^
in raise_an_exception_async
    raise Exception(f"In tool raise_an_exception_async: {s}") from e
Exception: In tool raise_an_exception_async: dummy_input
""".split(
        "\n"
    ),
}

if sys.version_info < (3, 11):
    # Python 3.11 on Mac has an extra line of ^^^^^ to point on the function raising the exception
    for key in expected_stack_traces:
        expected_stack_traces[key] = [line for line in expected_stack_traces[key] if re.match(r"^\s+\^+", line) is None]


@pytest.mark.e2etest
class TestExecutorFailures:
    @pytest.mark.parametrize(
        "flow_folder, node_name, message",
        [
            ("sync_tools_failures", "sync_fail", "In tool raise_an_exception: dummy_input"),
            ("async_tools_failures", "async_fail", "In tool raise_an_exception_async: dummy_input"),
        ],
    )
    def test_executor_exec_node_fail(self, flow_folder, node_name, message):
        yaml_file = get_yaml_file(flow_folder)
        run_info = FlowExecutor.load_and_exec_node(yaml_file, node_name)
        assert run_info.output is None
        assert run_info.status == Status.Failed
        assert isinstance(run_info.api_calls, list)
        assert len(run_info.api_calls) == 1
        assert run_info.node == node_name
        assert run_info.system_metrics["duration"] >= 0
        assert run_info.error is not None
        assert f"Execution failure in '{node_name}'" in run_info.error["message"]
        assert len(run_info.error["additionalInfo"]) == 1
        user_error_info_dict = run_info.error["additionalInfo"][0]
        assert "ToolExecutionErrorDetails" == user_error_info_dict["type"]
        user_error_info = user_error_info_dict["info"]
        assert message == user_error_info["message"]
        #  Make sure the stack trace is as expected
        stacktrace = user_error_info["traceback"].split("\n")
        expected_stack_trace = expected_stack_traces[flow_folder]
        if len(stacktrace) != len(expected_stack_trace):
            # actually we should fail now; adding this to make sure we can see the difference
            assert stacktrace == expected_stack_trace
        for expected_item, actual_item in zip(expected_stack_trace, stacktrace):
            assert expected_item in actual_item

    @pytest.mark.parametrize(
        "flow_folder, failed_node_name, message",
        [
            ("sync_tools_failures", "sync_fail", "In tool raise_an_exception: dummy_input"),
            ("async_tools_failures", "async_fail", "In tool raise_an_exception_async: dummy_input"),
        ],
    )
    def test_executor_exec_line_fail(self, flow_folder, failed_node_name, message):
        yaml_file = get_yaml_file(flow_folder)
        executor = FlowExecutor.create(yaml_file, {}, raise_ex=False)
        line_result = executor.exec_line({})
        run_info = line_result.run_info
        assert run_info.output is None
        assert run_info.status == Status.Failed
        assert isinstance(run_info.api_calls, list)
        assert len(run_info.api_calls) == 1
        assert run_info.system_metrics["duration"] >= 0
        assert run_info.error is not None
        assert f"Execution failure in '{failed_node_name}'" in run_info.error["message"]
        assert len(run_info.error["additionalInfo"]) == 1
        user_error_info_dict = run_info.error["additionalInfo"][0]
        assert "ToolExecutionErrorDetails" == user_error_info_dict["type"]
        user_error_info = user_error_info_dict["info"]
        assert message == user_error_info["message"]
        #  Make sure the stack trace is as expected
        stacktrace = user_error_info["traceback"].split("\n")
        expected_stack_trace = expected_stack_traces[flow_folder]
        if len(stacktrace) != len(expected_stack_trace):
            # actually we should fail now; adding this to make sure we can see the difference
            assert stacktrace == expected_stack_trace
        for expected_item, actual_item in zip(expected_stack_trace, stacktrace):
            assert expected_item in actual_item

    @pytest.mark.parametrize(
        "flow_folder, failed_node_name, message",
        [
            ("sync_tools_failures", "sync_fail", "In tool raise_an_exception: dummy_input"),
            ("async_tools_failures", "async_fail", "In tool raise_an_exception_async: dummy_input"),
        ],
    )
    def test_executor_exec_line_fail_with_exception(self, flow_folder, failed_node_name, message):
        yaml_file = get_yaml_file(flow_folder)
        # Here we set raise_ex to True to make sure the exception is raised and we can check the error detail.
        executor = FlowExecutor.create(yaml_file, {}, raise_ex=True)
        with pytest.raises(ToolExecutionError) as e:
            executor.exec_line({})
        ex = e.value
        assert ex.error_codes == ["UserError", "ToolExecutionError"]
        ex_str = str(ex)
        assert ex_str.startswith(f"Execution failure in '{failed_node_name}'")
        assert message in ex_str
        expected_stack_trace = expected_stack_traces[flow_folder]
        stacktrace = ex.tool_traceback.split("\n")
        #  Remove "^^^^^^^^" lines as they are not part of actual stack trace
        stacktrace = [line for line in stacktrace if "^^^^^^^^" not in line]
        assert len(stacktrace) == len(expected_stack_trace)
        for expected_item, actual_item in zip(expected_stack_trace, stacktrace):
            assert expected_item in actual_item
