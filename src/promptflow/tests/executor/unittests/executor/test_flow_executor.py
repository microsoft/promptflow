from unittest.mock import Mock, patch

import pytest

from promptflow import tool
from promptflow.contracts.flow import FlowInputDefinition
from promptflow.contracts.tool import ValueType
from promptflow.executor._line_execution_process_pool import get_available_max_worker_count
from promptflow.executor.flow_executor import (
    FlowExecutor,
    _ensure_node_result_is_serializable,
    _inject_stream_options,
    enable_streaming_for_llm_tool,
)
from promptflow.tools.aoai import AzureOpenAI, chat, completion


@pytest.mark.unittest
class TestFlowExecutor:
    @pytest.mark.parametrize(
        "flow_inputs, inputs, expected_inputs",
        [
            (
                {
                    "input_from_default": FlowInputDefinition(type=ValueType.STRING, default="default_value"),
                },
                None,  # Could handle None input
                {"input_from_default": "default_value"},
            ),
            (
                {
                    "input_from_default": FlowInputDefinition(type=ValueType.STRING, default="default_value"),
                },
                {},
                {"input_from_default": "default_value"},
            ),
            (
                {
                    "input_no_default": FlowInputDefinition(type=ValueType.STRING),
                },
                {},
                {},  # No default value for input.
            ),
            (
                {
                    "input_from_default": FlowInputDefinition(type=ValueType.STRING, default="default_value"),
                },
                {"input_from_default": "input_value", "another_key": "input_value"},
                {"input_from_default": "input_value", "another_key": "input_value"},
            ),
        ],
    )
    def test_apply_default_value_for_input(self, flow_inputs, inputs, expected_inputs):
        result = FlowExecutor._apply_default_value_for_input(flow_inputs, inputs)
        assert result == expected_inputs

    @pytest.mark.parametrize(
        "flow_inputs, aggregated_flow_inputs, aggregation_inputs, expected_inputs",
        [
            (
                {
                    "input_from_default": FlowInputDefinition(type=ValueType.STRING, default="default_value"),
                },
                {},
                {},
                {"input_from_default": ["default_value"]},
            ),
            (
                {
                    "input_no_default": FlowInputDefinition(type=ValueType.STRING),
                },
                {},
                {},
                {},  # No default value for input.
            ),
            (
                {
                    "input_from_default": FlowInputDefinition(type=ValueType.STRING, default="default_value"),
                },
                {"input_from_default": "input_value", "another_key": "input_value"},
                {},
                {"input_from_default": "input_value", "another_key": "input_value"},
            ),
            (
                {
                    "input_from_default": FlowInputDefinition(type=ValueType.STRING, default="default_value"),
                },
                {"another_key": ["input_value", "input_value"]},
                {},
                {
                    "input_from_default": ["default_value", "default_value"],
                    "another_key": ["input_value", "input_value"],
                },
            ),
            (
                {
                    "input_from_default": FlowInputDefinition(type=ValueType.STRING, default="default_value"),
                },
                {},
                {"another_key_in_aggregation_inputs": ["input_value", "input_value"]},
                {
                    "input_from_default": ["default_value", "default_value"],
                },
            ),
        ],
    )
    def test_apply_default_value_for_aggregation_input(
        self, flow_inputs, aggregated_flow_inputs, aggregation_inputs, expected_inputs
    ):
        result = FlowExecutor._apply_default_value_for_aggregation_input(
            flow_inputs, aggregated_flow_inputs, aggregation_inputs
        )
        assert result == expected_inputs


def func_with_stream_parameter(a: int, b: int, stream=False):
    return a + b, stream


def func_without_stream_parameter(a: int, b: int):
    return a + b


class TestEnableStreamForLLMTool:
    @pytest.mark.parametrize(
        "tool, should_be_wrapped",
        [
            (completion, True),
            (chat, True),
            (AzureOpenAI.embedding, False),
        ],
    )
    def test_enable_stream_for_llm_tool(self, tool, should_be_wrapped):
        func = enable_streaming_for_llm_tool(tool)
        is_wrapped = func != tool
        assert is_wrapped == should_be_wrapped

    def test_func_with_stream_parameter_should_be_wrapped(self):
        func = enable_streaming_for_llm_tool(func_with_stream_parameter)
        assert func != func_with_stream_parameter

        result = func(a=1, b=2)
        assert result == (3, True)

        result = func_with_stream_parameter(a=1, b=2)
        assert result == (3, False)

    def test_func_without_stream_parameter_should_not_be_wrapped(self):
        func = enable_streaming_for_llm_tool(func_without_stream_parameter)
        assert func == func_without_stream_parameter

        result = func(a=1, b=2)
        assert result == 3

    def test_inject_stream_options_no_stream_param(self):
        # Test that the function does not wrap the decorated function if it has no stream parameter
        func = _inject_stream_options(lambda: True)(func_without_stream_parameter)
        assert func == func_without_stream_parameter

        result = func(a=1, b=2)
        assert result == 3

    def test_inject_stream_options_with_stream_param(self):
        # Test that the function wraps the decorated function and injects the stream option
        func = _inject_stream_options(lambda: True)(func_with_stream_parameter)
        assert func != func_with_stream_parameter

        result = func(a=1, b=2)
        assert result == (3, True)

        result = func_with_stream_parameter(a=1, b=2)
        assert result == (3, False)

    def test_inject_stream_options_with_mocked_should_stream(self):
        # Test that the function uses the should_stream callable to determine the stream option
        should_stream = Mock(return_value=True)

        func = _inject_stream_options(should_stream)(func_with_stream_parameter)
        result = func(a=1, b=2)
        assert result == (3, True)

        should_stream.return_value = False
        result = func(a=1, b=2)
        assert result == (3, False)


@tool
def streaming_tool():
    for i in range(10):
        yield i


@tool
def non_streaming_tool():
    return 1


class TestEnsureNodeResultIsSerializable:
    def test_streaming_tool_should_be_consumed_and_merged(self):
        func = _ensure_node_result_is_serializable(streaming_tool)
        assert func() == "0123456789"

    def test_non_streaming_tool_should_not_be_affected(self):
        func = _ensure_node_result_is_serializable(non_streaming_tool)
        assert func() == 1


class TestGetAvailableMaxWorkerCount:
    @pytest.mark.parametrize(
        "total_memory, available_memory, process_memory, expected_max_worker_count, actual_calculate_worker_count",
        [
            (1024.0, 128.0, 64.0, 1, -3),  # available_memory - 0.3 * total_memory < 0
            (1024.0, 307.20, 64.0, 1, 0),  # available_memory - 0.3 * total_memory = 0
            (1024.0, 768.0, 64.0, 7, 7),  # available_memory - 0.3 * total_memory > 0
        ],
    )
    def test_get_available_max_worker_count(
        self, total_memory, available_memory, process_memory, expected_max_worker_count, actual_calculate_worker_count
    ):
        with patch("psutil.virtual_memory") as mock_mem:
            mock_mem.return_value.total = total_memory * 1024 * 1024
            mock_mem.return_value.available = available_memory * 1024 * 1024
            with patch("psutil.Process") as mock_process:
                mock_process.return_value.memory_info.return_value.rss = process_memory * 1024 * 1024
                with patch("promptflow.executor._line_execution_process_pool.logger") as mock_logger:
                    mock_logger.warning.return_value = None
                    max_worker_count = get_available_max_worker_count()
                    assert max_worker_count == expected_max_worker_count
                    if actual_calculate_worker_count < 1:
                        mock_logger.warning.assert_called_with(
                            f"Available max worker count {actual_calculate_worker_count} is less than 1, "
                            "set it to 1."
                        )
