import json
from unittest.mock import Mock

import pytest

from promptflow import tool
from promptflow.executor.flow_executor import (
    EmptyInputListError,
    EmptyInputMappingError,
    FlowExecutor,
    LineNumberNotAlign,
    MappingSourceNotFound,
    enable_streaming_for_llm_tool,
    ensure_node_result_is_serializable,
    inject_stream_options,
)
from promptflow.tools.aoai import chat, completion, embedding


@pytest.mark.unittest
class TestFlowExecutor:
    @pytest.mark.parametrize(
        "inputs, inputs_mapping, expected",
        [
            (
                {
                    "data": {"answer": 123, "question": "dummy"},
                    "output": {"answer": 321},
                    "baseline": {"answer": 322},
                },
                {
                    "question": "data.question",  # Question from the data
                    "groundtruth": "data.answer",  # Answer from the data
                    "baseline": "baseline.answer",  # Answer from the baseline
                    "answer": "output.answer",  # Answer from the output
                    "deployment_name": "text-davinci-003",  # literal value
                },
                {
                    "question": "dummy",
                    "groundtruth": 123,
                    "baseline": 322,
                    "answer": 321,
                    "deployment_name": "text-davinci-003",
                },
            ),
        ],
    )
    def test_inputs_mapping_legacy(self, inputs, inputs_mapping, expected):
        result = FlowExecutor.apply_inputs_mapping_legacy(inputs, inputs_mapping)
        assert expected == result, "Expected: {}, Actual: {}".format(expected, result)

    def test_inputs_mapping_legacy_not_found_key(self):
        inputs = {
            "data": {"answer": "ans1", "answer2": "ans2"},
        }
        mapping = {"question": "data.question"}
        with pytest.raises(MappingSourceNotFound) as e:
            FlowExecutor.apply_inputs_mapping_legacy(inputs, mapping)
        error_message = (
            "Failed to do input mapping for 'data.question', can't find key 'question' in dict 'data', "
            "all keys are dict_keys(['answer', 'answer2'])."
        )
        assert error_message == str(e.value), "Expected: {}, Actual: {}".format(error_message, str(e.value))

    @pytest.mark.parametrize(
        "inputs, inputs_mapping, expected",
        [
            (
                {
                    "data.test": {"question": "longer input key has lower priority."},
                },
                {
                    "question": "${data.test.question}",  # Question from the data
                },
                {
                    "question": "longer input key has lower priority.",
                },
            ),
            (
                {
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
    def test_inputs_mapping(self, inputs, inputs_mapping, expected):
        result = FlowExecutor.apply_inputs_mapping(inputs, inputs_mapping)
        assert expected == result, "Expected: {}, Actual: {}".format(expected, result)

    @pytest.mark.parametrize(
        "inputs, inputs_mapping, error_message",
        [
            (
                {
                    "data": {"answer": 123, "question": "dummy"},
                    "baseline": {"answer": 123, "question": "dummy"},
                },
                {
                    "question": "${baseline.output}",  # Question from the data
                },
                "Failed to do input mapping for '${baseline.output}', can't find corresponding input.",
            ),
        ],
    )
    def test_inputs_mapping_not_found_key(self, inputs, inputs_mapping, error_message):
        with pytest.raises(MappingSourceNotFound) as e:
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
                    {"data": {"question": "q1", "answer": "ans1"}, "output": {"answer": "output_ans1"}},
                    {"data": {"question": "q2", "answer": "ans2"}, "output": {"answer": "output_ans2"}},
                ],
            ),
            (
                {
                    "data": [{"question": "q1", "answer": "ans1"}, {"question": "q2", "answer": "ans2"}],
                    "output": [{"answer": "output_ans2", "line_number": 1}],
                },
                [
                    {
                        "data": {"question": "q2", "answer": "ans2"},
                        "output": {"answer": "output_ans2", "line_number": 1},
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

    @pytest.mark.parametrize(
        "inputs, inputs_mapping, expected",
        [
            (
                {
                    "data": [{"question": "q1", "answer": "ans1"}, {"question": "q2", "answer": "ans2"}],
                },
                {},
                # Single input and empty mapping, should return the value from input.
                [{"question": "q1", "answer": "ans1"}, {"question": "q2", "answer": "ans2"}],
            ),
            (
                {
                    "data": [{"question": "q1", "answer": "ans1"}, {"question": "q2", "answer": "ans2"}],
                },
                {
                    "question": "${data.question}",  # Question from the data
                    "groundtruth": "${data.answer}",  # Answer from the data
                },
                [
                    {
                        "question": "q1",
                        "groundtruth": "ans1",
                    },
                    {
                        "question": "q2",
                        "groundtruth": "ans2",
                    },
                ],
            ),
            (
                {
                    "data": [{"question": "q1", "answer": "ans1"}, {"question": "q2", "answer": "ans2"}],
                    "baseline": [{"answer": "baseline_ans2", "line_number": 1}],
                },
                {
                    "question": "${data.question}",  # Question from the data
                    "groundtruth": "${data.answer}",  # Answer from the data
                    "baseline": "${baseline.answer}",  # Answer from the baseline
                    "deployment_name": "text-davinci-003",  # literal value
                    "line_number": "${baseline.line_number}",  # Line number from the baseline
                },
                [
                    {
                        "question": "q2",
                        "groundtruth": "ans2",
                        "baseline": "baseline_ans2",
                        "line_number": 1,
                        "deployment_name": "text-davinci-003",
                    },
                ],
            ),
            (
                {
                    "data": [{"question": "q1", "answer": "ans1"}, {"question": "q2", "answer": "ans2"}],
                    "baseline": [{"answer": "baseline_ans1"}, {"answer": "baseline_ans2"}],
                },
                {
                    "question": "${data.question}",  # Question from the data
                    "groundtruth": "${data.answer}",  # Answer from the data
                    "baseline": "${baseline.answer}",  # Answer from the baseline
                    "deployment_name": "text-davinci-003",  # literal value
                },
                [
                    {
                        "question": "q1",
                        "groundtruth": "ans1",
                        "baseline": "baseline_ans1",
                        "deployment_name": "text-davinci-003",
                    },
                    {
                        "question": "q2",
                        "groundtruth": "ans2",
                        "baseline": "baseline_ans2",
                        "deployment_name": "text-davinci-003",
                    },
                ],
            ),
        ],
    )
    def test_inputs_mapping_for_all_lines(self, inputs, inputs_mapping, expected):
        result = FlowExecutor.apply_inputs_mapping_for_all_lines(inputs, inputs_mapping)
        assert expected == result, "Expected: {}, Actual: {}".format(expected, result)

    @pytest.mark.parametrize(
        "inputs, inputs_mapping, error_code, error_message",
        [
            (
                {
                    "data": [{"question": "q1", "answer": "ans1"}, {"question": "q2", "answer": "ans2"}],
                    "data2": [{"question": "q1", "answer": "ans1"}, {"question": "q2", "answer": "ans2"}],
                },
                {},
                EmptyInputMappingError,
                "inputs_mapping is empty and there are more than one input.",
            ),
        ],
    )
    def test_inputs_mapping_for_all_lines_error(self, inputs, inputs_mapping, error_code, error_message):
        with pytest.raises(error_code) as e:
            FlowExecutor.apply_inputs_mapping_for_all_lines(inputs, inputs_mapping)
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
            (embedding, False),
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
        func = inject_stream_options(lambda: True)(func_without_stream_parameter)
        assert func == func_without_stream_parameter

        result = func(a=1, b=2)
        assert result == 3

    def test_inject_stream_options_with_stream_param(self):
        # Test that the function wraps the decorated function and injects the stream option
        func = inject_stream_options(lambda: True)(func_with_stream_parameter)
        assert func != func_with_stream_parameter

        result = func(a=1, b=2)
        assert result == (3, True)

        result = func_with_stream_parameter(a=1, b=2)
        assert result == (3, False)

    def test_inject_stream_options_with_mocked_should_stream(self):
        # Test that the function uses the should_stream callable to determine the stream option
        should_stream = Mock(return_value=True)

        func = inject_stream_options(should_stream)(func_with_stream_parameter)
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
        func = ensure_node_result_is_serializable(streaming_tool)
        assert func() == "0123456789"

    def test_non_streaming_tool_should_not_be_affected(self):
        func = ensure_node_result_is_serializable(non_streaming_tool)
        assert func() == 1
