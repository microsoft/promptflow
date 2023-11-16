import uuid
from types import GeneratorType

import pytest

from promptflow._utils.dataclass_serializer import serialize
from promptflow.batch._batch_inputs_processor import BatchInputsProcessor
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
)

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
in _invoke_tool_with_timer
    return f(**kwargs)
in decorated_tool
    output = func(*args, **kwargs)
sync_fail.py", line 13, in raise_an_exception
    raise Exception(f"In tool raise_an_exception: {s}") from e
Exception: In tool raise_an_exception: dummy_input
""".split("\n"),
    "async_tools_failures": """Traceback (most recent call last):
async_fail.py", line 11, in raise_an_exception_async
    await raise_exception_async(s)
async_fail.py", line 5, in raise_exception_async
    raise Exception(msg)
Exception: In raise_exception_async: dummy_input

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
, in _invoke_tool_async_inner
    return await f(**kwargs)
in decorated_tool
    output = await func(*args, **kwargs)
in raise_an_exception_async
    raise Exception(f"In tool raise_an_exception_async: {s}") from e
Exception: In tool raise_an_exception_async: dummy_input
""".split("\n"),
}


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
        assert len(stacktrace) == len(expected_stack_trace)
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
        assert len(stacktrace) == len(expected_stack_trace)
        for expected_item, actual_item in zip(expected_stack_trace, stacktrace):
            assert expected_item in actual_item
