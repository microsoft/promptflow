import json
from unittest.mock import Mock, patch

import pytest

from promptflow import tool
from promptflow._core._errors import UnexpectedError
from promptflow.contracts.flow import Flow, FlowInputDefinition
from promptflow.contracts.tool import ValueType
from promptflow.executor._errors import InvalidAggregationInput
from promptflow.executor._line_execution_process_pool import get_available_max_worker_count
from promptflow.executor.flow_executor import (
    FlowExecutor,
    InputMappingError,
    _ensure_node_result_is_serializable,
    _inject_stream_options,
    enable_streaming_for_llm_tool,
)
from promptflow.tools.aoai import AzureOpenAI, chat, completion


@pytest.mark.unittest
class TestFlowExecutor:
    @pytest.mark.parametrize(
        "inputs, inputs_mapping, expected",
        [
            (
                {"data.test": {"question": "longer input key has lower priority."}, "line_number": 1},
                {
                    "question": "${data.test.question}",  # Question from the data
                },
                {"question": "longer input key has lower priority.", "line_number": 1},
            ),
            (
                {
                    # Missing line_number is also valid data.
                    "data.test": {"question": "longer input key has lower priority."},
                    "data": {"test.question": "Shorter input key has higher priority."},
                },
                {
                    "question": "${data.test.question}",  # Question from the data
                    "deployment_name": "text-davinci-003",  # literal value
                },
                {
                    "question": "Shorter input key has higher priority.",
                    "deployment_name": "text-davinci-003",
                },
            ),
        ],
    )
    def test_apply_inputs_mapping(self, inputs, inputs_mapping, expected):
        result = FlowExecutor.apply_inputs_mapping(inputs, inputs_mapping)
        assert expected == result, "Expected: {}, Actual: {}".format(expected, result)

    @pytest.mark.parametrize(
        "inputs, inputs_mapping, error_code, error_message",
        [
            (
                {
                    "baseline": {"answer": 123, "question": "dummy"},
                },
                {
                    "question": "${baseline.output}",
                    "answer": "${data.output}",
                },
                InputMappingError,
                "The input for flow is incorrect. Couldn't find these mapping relations: ${baseline.output}, "
                "${data.output}. Please make sure your input mapping keys and values match your YAML input section "
                "and input data. If a mapping reads input from 'data', it might be generated from the YAML input "
                "section, and you may need to manually assign input mapping based on your input data.",
            ),
        ],
    )
    def test_apply_inputs_mapping_error(self, inputs, inputs_mapping, error_code, error_message):
        with pytest.raises(error_code) as e:
            FlowExecutor.apply_inputs_mapping(inputs, inputs_mapping)
        assert error_message == str(e.value), "Expected: {}, Actual: {}".format(error_message, str(e.value))

    @pytest.mark.parametrize(
        "inputs, expected",
        [
            (
                {
                    "data": [{"question": "q1", "answer": "ans1"}, {"question": "q2", "answer": "ans2"}],
                    "output": [{"answer": "output_ans1"}, {"answer": "output_ans2"}],
                },
                [
                    # Get 2 lines data.
                    {
                        "data": {"question": "q1", "answer": "ans1"},
                        "output": {"answer": "output_ans1"},
                        "line_number": 0,
                    },
                    {
                        "data": {"question": "q2", "answer": "ans2"},
                        "output": {"answer": "output_ans2"},
                        "line_number": 1,
                    },
                ],
            ),
            (
                {
                    "data": [{"question": "q1", "answer": "ans1"}, {"question": "q2", "answer": "ans2"}],
                    "output": [{"answer": "output_ans2", "line_number": 1}],
                },
                [
                    # Only one line valid data.
                    {
                        "data": {"question": "q2", "answer": "ans2"},
                        "output": {"answer": "output_ans2", "line_number": 1},
                        "line_number": 1,
                    },
                ],
            ),
        ],
    )
    def test_merge_input_dicts_by_line(self, inputs, expected):
        result = FlowExecutor._merge_input_dicts_by_line(inputs)
        json.dumps(result)
        assert expected == result, "Expected: {}, Actual: {}".format(expected, result)

    @pytest.mark.parametrize(
        "inputs, error_code, error_message",
        [
            (
                {
                    "baseline": [],
                },
                InputMappingError,
                "The input for flow is incorrect. Input from key 'baseline' is an empty list, which means we "
                "cannot generate a single line input for the flow run. Please rectify the input and try again.",
            ),
            (
                {
                    "data": [{"question": "q1", "answer": "ans1"}, {"question": "q2", "answer": "ans2"}],
                    "baseline": [{"answer": "baseline_ans2"}],
                },
                InputMappingError,
                "The input for flow is incorrect. Line numbers are not aligned. Some lists have dictionaries missing "
                "the 'line_number' key, and the lengths of these lists are different. List lengths are: "
                "{'data': 2, 'baseline': 1}. Please make sure these lists have the same length "
                "or add 'line_number' key to each dictionary.",
            ),
        ],
    )
    def test_merge_input_dicts_by_line_error(self, inputs, error_code, error_message):
        with pytest.raises(error_code) as e:
            FlowExecutor._merge_input_dicts_by_line(inputs)
        assert error_message == str(e.value), "Expected: {}, Actual: {}".format(error_message, str(e.value))

    @pytest.mark.parametrize("inputs_mapping", [{"question": "${data.question}"}, {}])
    def test_complete_inputs_mapping_by_default_value(self, inputs_mapping):
        inputs = {
            "question": None,
            "groundtruth": None,
            "input_with_default_value": FlowInputDefinition(type=ValueType.INT, default="default_value"),
        }
        flow = Flow(id="fakeId", name=None, nodes=[], inputs=inputs, outputs=None, tools=[])
        flow_executor = FlowExecutor(
            flow=flow,
            connections=None,
            run_tracker=None,
            cache_manager=None,
            loaded_tools=None,
        )
        updated_inputs_mapping = flow_executor._complete_inputs_mapping_by_default_value(inputs_mapping)
        assert "input_with_default_value" not in updated_inputs_mapping
        assert updated_inputs_mapping == {"question": "${data.question}", "groundtruth": "${data.groundtruth}"}

    @pytest.mark.parametrize(
        "inputs, inputs_mapping, expected",
        [
            (
                # Use default mapping generated from flow inputs.
                {
                    "data": [{"question": "q1", "groundtruth": "ans1"}, {"question": "q2", "groundtruth": "ans2"}],
                },
                {},
                [
                    {
                        "question": "q1",
                        "groundtruth": "ans1",
                        "line_number": 0,
                    },
                    {
                        "question": "q2",
                        "groundtruth": "ans2",
                        "line_number": 1,
                    },
                ],
            ),
            (
                # Partially use default mapping generated from flow inputs.
                {
                    "data": [{"question": "q1", "groundtruth": "ans1"}, {"question": "q2", "groundtruth": "ans2"}],
                },
                {
                    "question": "${data.question}",
                },
                [
                    {
                        "question": "q1",
                        "groundtruth": "ans1",
                        "line_number": 0,
                    },
                    {
                        "question": "q2",
                        "groundtruth": "ans2",
                        "line_number": 1,
                    },
                ],
            ),
            (
                {
                    "data": [
                        {"question": "q1", "answer": "ans1", "line_number": 5},
                        {"question": "q2", "answer": "ans2", "line_number": 6},
                    ],
                    "baseline": [
                        {"answer": "baseline_ans1", "line_number": 5},
                        {"answer": "baseline_ans2", "line_number": 7},
                    ],
                },
                {
                    "question": "${data.question}",  # Question from the data
                    "groundtruth": "${data.answer}",  # Answer from the data
                    "baseline": "${baseline.answer}",  # Answer from the baseline
                    "deployment_name": "text-davinci-003",  # literal value
                    "line_number": "${data.question}",  # line_number mapping should be ignored
                },
                [
                    {
                        "question": "q1",
                        "groundtruth": "ans1",
                        "baseline": "baseline_ans1",
                        "deployment_name": "text-davinci-003",
                        "line_number": 5,
                    },
                ],
            ),
        ],
    )
    def test_validate_and_apply_inputs_mapping(self, inputs, inputs_mapping, expected):
        flow = Flow(
            id="fakeId", name=None, nodes=[], inputs={"question": None, "groundtruth": None}, outputs=None, tools=[]
        )
        flow_executor = FlowExecutor(
            flow=flow,
            connections=None,
            run_tracker=None,
            cache_manager=None,
            loaded_tools=None,
        )
        result = flow_executor.validate_and_apply_inputs_mapping(inputs, inputs_mapping)
        assert expected == result, "Expected: {}, Actual: {}".format(expected, result)

    def test_validate_and_apply_inputs_mapping_empty_input(self):
        flow = Flow(id="fakeId", name=None, nodes=[], inputs={}, outputs=None, tools=[])
        flow_executor = FlowExecutor(
            flow=flow,
            connections=None,
            run_tracker=None,
            cache_manager=None,
            loaded_tools=None,
        )
        inputs = {
            "data": [{"question": "q1", "answer": "ans1"}, {"question": "q2", "answer": "ans2"}],
            "baseline": [{"answer": "baseline_ans1"}, {"answer": "baseline_ans2"}],
        }
        result = flow_executor.validate_and_apply_inputs_mapping(inputs, {})
        assert result == [
            {"line_number": 0},
            {"line_number": 1},
        ], "Empty flow inputs and inputs_mapping should return list with empty dicts."

    @pytest.mark.parametrize(
        "inputs_mapping, error_code",
        [
            (
                {"question": "${question}"},
                InputMappingError,
            ),
        ],
    )
    def test_validate_and_apply_inputs_mapping_error(self, inputs_mapping, error_code):
        flow = Flow(id="fakeId", name=None, nodes=[], inputs={"question": None}, outputs=None, tools=[])
        flow_executor = FlowExecutor(
            flow=flow,
            connections=None,
            run_tracker=None,
            cache_manager=None,
            loaded_tools=None,
        )
        with pytest.raises(error_code) as _:
            flow_executor.validate_and_apply_inputs_mapping(inputs={}, inputs_mapping=inputs_mapping)

    @pytest.mark.parametrize(
        "inputs, inputs_mapping, error_code, error_message",
        [
            (
                {
                    "data": [{"question": "q1", "answer": "ans1"}, {"question": "q2", "answer": "ans2"}],
                },
                None,
                UnexpectedError,
                "Input mapping is None. You need to set one input mapping or use default input mapping. "
                "Please contact support for further assistance.",
            ),
        ],
    )
    def test_inputs_mapping_for_all_lines_error(self, inputs, inputs_mapping, error_code, error_message):
        with pytest.raises(error_code) as e:
            FlowExecutor._apply_inputs_mapping_for_all_lines(inputs, inputs_mapping)
        assert error_message == str(e.value), "Expected: {}, Actual: {}".format(error_message, str(e.value))

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

    @pytest.mark.parametrize(
        "aggregated_flow_inputs, aggregation_inputs, error_message",
        [
            (
                {},
                {
                    "input1": "value1",
                },
                "Aggregation input input1 should be one list.",
            ),
            (
                {
                    "input1": "value1",
                },
                {},
                "Flow aggregation input input1 should be one list.",
            ),
            (
                {"input1": ["value1_1", "value1_2"]},
                {"input_2": ["value2_1"]},
                "Whole aggregation inputs should have the same length. "
                "Current key length mapping are: {'input1': 2, 'input_2': 1}",
            ),
            (
                {
                    "input1": "value1",
                },
                {
                    "input1": "value1",
                },
                "Input 'input1' appear in both flow aggregation input and aggregation input.",
            ),
        ],
    )
    def test_validate_aggregation_inputs_error(self, aggregated_flow_inputs, aggregation_inputs, error_message):
        with pytest.raises(InvalidAggregationInput) as e:
            FlowExecutor._validate_aggregation_inputs(aggregated_flow_inputs, aggregation_inputs)
        assert str(e.value) == error_message


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
