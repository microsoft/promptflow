import json
from pathlib import Path
from tempfile import mkdtemp

import pytest

from promptflow._core._errors import UnexpectedError
from promptflow._utils._errors import ApplyInputMappingError
from promptflow._utils.inputs_mapping_utils import apply_inputs_mapping
from promptflow._utils.utils import dump_list_to_jsonl
from promptflow.batch._batch_inputs_processor import BatchInputsProcessor
from promptflow.batch._errors import EmptyInputsData, InputMappingError
from promptflow.contracts.flow import FlowInputDefinition
from promptflow.contracts.tool import ValueType

from ...utils import DATA_ROOT


@pytest.mark.unittest
class TestBatchInputsProcessor:
    def test_process_batch_inputs(self):
        data = [
            {"question": "What's promptflow?"},
            {"question": "Do you like promptflow?"},
        ]
        data_file = Path(mkdtemp()) / "data.jsonl"
        dump_list_to_jsonl(data_file, data)
        input_dirs = {"data": data_file}
        inputs_mapping = {"question": "${data.question}"}
        batch_inputs = BatchInputsProcessor("", {}).process_batch_inputs(input_dirs, inputs_mapping)
        assert batch_inputs == [
            {"line_number": 0, "question": "What's promptflow?"},
            {"line_number": 1, "question": "Do you like promptflow?"},
        ]

    def test_process_batch_inputs_error(self):
        data_file = Path(mkdtemp()) / "data.jsonl"
        data_file.touch()
        input_dirs = {"data": data_file}
        inputs_mapping = {"question": "${data.question}"}
        with pytest.raises(EmptyInputsData) as e:
            BatchInputsProcessor("", {}).process_batch_inputs(input_dirs, inputs_mapping)
        expected_error_message = (
            "Couldn't find any inputs data at the given input paths. "
            "Please review the provided path and consider resubmitting."
        )
        assert expected_error_message in e.value.message

    def test_process_batch_inputs_without_inputs_mapping(self):
        questions = [
            {"question": "What's promptflow?"},
            {"question": "Do you like promptflow?"},
        ]
        topics = [
            {"topic": "fruit"},
            {"topic": "sport"},
        ]
        questions_data_file = Path(mkdtemp()) / "questions.jsonl"
        topics_data_file = Path(mkdtemp()) / "topics.jsonl"
        dump_list_to_jsonl(questions_data_file, questions)
        dump_list_to_jsonl(topics_data_file, topics)
        input_dirs = {"question": questions_data_file, "topic": topics_data_file}
        batch_inputs = BatchInputsProcessor("", {}).process_batch_inputs_without_inputs_mapping(input_dirs)
        assert batch_inputs == [
            {"line_number": 0, "question": {"question": "What's promptflow?"}, "topic": {"topic": "fruit"}},
            {"line_number": 1, "question": {"question": "Do you like promptflow?"}, "topic": {"topic": "sport"}},
        ]

    def test_resolve_data_from_input_path(self):
        inputs_dir = Path(mkdtemp())
        # data.jsonl
        data = [
            {"question": "What's promptflow?"},
            {"question": "Do you like promptflow?"},
        ]
        data_file = inputs_dir / "data.jsonl"
        dump_list_to_jsonl(data_file, data)
        # inputs.json
        inputs_file = inputs_dir / "inputs.json"
        with open(inputs_file, "w") as file:
            file.write(json.dumps(data))

        result = BatchInputsProcessor("", {})._resolve_data_from_input_path(inputs_dir)
        assert result == data + data

        # if has max_lines_count
        result = BatchInputsProcessor("", {}, max_lines_count=1)._resolve_data_from_input_path(inputs_dir)
        assert result == [
            {"question": "What's promptflow?"},
        ]

    @pytest.mark.parametrize(
        "data_path",
        [
            "10k.jsonl",
            "10k",
        ],
    )
    def test_resolve_data_from_input_path_with_large_data(self, data_path):
        data_path = DATA_ROOT / "load_data_cases" / data_path
        result = BatchInputsProcessor("", {})._resolve_data_from_input_path(Path(data_path))
        assert isinstance(result, list)
        assert len(result) == 10000

        # specify max_rows_count
        max_rows_count = 5
        head_results = BatchInputsProcessor(
            working_dir="",
            flow_inputs={},
            max_lines_count=max_rows_count,
        )._resolve_data_from_input_path(Path(data_path))
        assert isinstance(head_results, list)
        assert len(head_results) == max_rows_count
        assert result[:max_rows_count] == head_results

    @pytest.mark.parametrize(
        "inputs, inputs_mapping, expected",
        [
            (
                {"data.test": {"question": "longer input key has lower priority."}, "line_number": 0},
                {
                    "question": "${data.test.question}",  # Question from the data
                    "value": 1,
                },
                {"question": "longer input key has lower priority.", "value": 1, "line_number": 0},
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
        result = apply_inputs_mapping(inputs, inputs_mapping)
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
                ApplyInputMappingError,
                "Couldn't find these mapping relations: ${baseline.output}, ${data.output}. "
                "Please make sure your input mapping keys and values match your YAML input section and input data.",
            ),
        ],
    )
    def test_apply_inputs_mapping_error(self, inputs, inputs_mapping, error_code, error_message):
        with pytest.raises(error_code) as e:
            apply_inputs_mapping(inputs, inputs_mapping)
        assert error_message in str(e.value), "Expected: {}, Actual: {}".format(error_message, str(e.value))

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
        result = BatchInputsProcessor("", {})._merge_input_dicts_by_line(inputs)
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
                "The input for batch run is incorrect. Input from key 'baseline' is an empty list, which means we "
                "cannot generate a single line input for the flow run. Please rectify the input and try again.",
            ),
            (
                {
                    "data": [{"question": "q1", "answer": "ans1"}, {"question": "q2", "answer": "ans2"}],
                    "baseline": [{"answer": "baseline_ans2"}],
                },
                InputMappingError,
                "The input for batch run is incorrect. Line numbers are not aligned. Some lists have dictionaries "
                "missing the 'line_number' key, and the lengths of these lists are different. List lengths are: "
                "{'data': 2, 'baseline': 1}. Please make sure these lists have the same length "
                "or add 'line_number' key to each dictionary.",
            ),
        ],
    )
    def test_merge_input_dicts_by_line_error(self, inputs, error_code, error_message):
        with pytest.raises(error_code) as e:
            BatchInputsProcessor("", {})._merge_input_dicts_by_line(inputs)
        assert error_message == str(e.value), "Expected: {}, Actual: {}".format(error_message, str(e.value))

    @pytest.mark.parametrize("inputs_mapping", [{"question": "${data.question}"}, {}])
    def test_complete_inputs_mapping_by_default_value(self, inputs_mapping):
        inputs = {
            "question": None,
            "groundtruth": None,
            "input_with_default_value": FlowInputDefinition(type=ValueType.BOOL, default=False),
        }
        updated_inputs_mapping = BatchInputsProcessor("", inputs)._complete_inputs_mapping_by_default_value(
            inputs_mapping
        )
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
        flow_inputs = {"question": None, "groundtruth": None}
        result = BatchInputsProcessor("", flow_inputs)._validate_and_apply_inputs_mapping(inputs, inputs_mapping)
        assert expected == result, "Expected: {}, Actual: {}".format(expected, result)

    def test_validate_and_apply_inputs_mapping_empty_input(self):
        inputs = {
            "data": [{"question": "q1", "answer": "ans1"}, {"question": "q2", "answer": "ans2"}],
            "baseline": [{"answer": "baseline_ans1"}, {"answer": "baseline_ans2"}],
        }
        result = BatchInputsProcessor("", {})._validate_and_apply_inputs_mapping(inputs, {})
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
        flow_inputs = {"question": None}
        with pytest.raises(error_code) as _:
            BatchInputsProcessor("", flow_inputs)._validate_and_apply_inputs_mapping(
                inputs={}, inputs_mapping=inputs_mapping
            )

    @pytest.mark.parametrize(
        "inputs, inputs_mapping, error_code, error_message",
        [
            (
                {
                    "data": [{"question": "q1", "answer": "ans1"}, {"question": "q2", "answer": "ans2"}],
                },
                None,
                UnexpectedError,
                "The input for batch run is incorrect. Please make sure to set up a proper input mapping "
                "before proceeding. If you need additional help, feel free to contact support for further assistance.",
            ),
        ],
    )
    def test_inputs_mapping_for_all_lines_error(self, inputs, inputs_mapping, error_code, error_message):
        with pytest.raises(error_code) as e:
            BatchInputsProcessor("", {})._apply_inputs_mapping_for_all_lines(inputs, inputs_mapping)
        assert error_message == str(e.value), "Expected: {}, Actual: {}".format(error_message, str(e.value))
