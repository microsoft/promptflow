import json
from unittest.mock import Mock

import pytest

from promptflow import tool
from promptflow.contracts.flow import Flow
from promptflow.executor.flow_executor import (
    EmptyInputAfterMapping,
    EmptyInputListError,
    FlowExecutor,
    LineNumberNotAlign,
    MappingSourceNotFound,
    NoneInputsMappingIsNotSupported,
    enable_streaming_for_llm_tool,
    _ensure_node_result_is_serializable,
    _inject_stream_options,
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
                MappingSourceNotFound,
                "Couldn't find these mapping relations: ${baseline.output}, ${data.output}. "
                "Please make sure your input mapping keys and values match your YAML input section and input data. "
                "If a mapping value has a '${data' prefix, it might be generated from the YAML input section, "
                "and you may need to manually assign input mapping based on your input data."
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
                EmptyInputListError,
                "List from key 'baseline' is empty.",
            ),
            (
                {
                    "data": [{"question": "q1", "answer": "ans1"}, {"question": "q2", "answer": "ans2"}],
                    "baseline": [{"answer": "baseline_ans2"}],
                },
                LineNumberNotAlign,
                "Line numbers are not aligned. Some lists have dictionaries missing the 'line_number' key, "
                "and the lengths of these lists are different. List lengths: {'data': 2, 'baseline': 1}",
            ),
        ],
    )
    def test_merge_input_dicts_by_line_error(self, inputs, error_code, error_message):
        with pytest.raises(error_code) as e:
            FlowExecutor._merge_input_dicts_by_line(inputs)
        assert error_message == str(e.value), "Expected: {}, Actual: {}".format(error_message, str(e.value))

    @pytest.mark.parametrize("inputs_mapping", [{"question": "${data.question}"}, {}])
    def test_complete_inputs_mapping_by_default_value(self, inputs_mapping):
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
        updated_inputs_mapping = flow_executor._complete_inputs_mapping_by_default_value(inputs_mapping)
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
                EmptyInputAfterMapping,
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
                NoneInputsMappingIsNotSupported,
                "Inputs mapping is None.",
            ),
        ],
    )
    def test_inputs_mapping_for_all_lines_error(self, inputs, inputs_mapping, error_code, error_message):
        with pytest.raises(error_code) as e:
            FlowExecutor._apply_inputs_mapping_for_all_lines(inputs, inputs_mapping)
        assert error_message == str(e.value), "Expected: {}, Actual: {}".format(error_message, str(e.value))


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
