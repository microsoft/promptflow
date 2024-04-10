# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from promptflow._constants import LINE_NUMBER_KEY, MessageFormatType
from promptflow._core._errors import UnexpectedError
from promptflow._utils.inputs_mapping_utils import apply_inputs_mapping
from promptflow._utils.load_data import load_data
from promptflow._utils.logger_utils import logger
from promptflow._utils.multimedia_utils import MultimediaProcessor
from promptflow._utils.utils import resolve_dir_to_absolute
from promptflow.batch._errors import EmptyInputsData, InputMappingError
from promptflow.contracts.flow import FlowInputDefinition


class BatchInputsProcessor:
    def __init__(
        self,
        working_dir: Path,
        flow_inputs: Mapping[str, FlowInputDefinition],
        max_lines_count: Optional[int] = None,
        message_format: str = MessageFormatType.BASIC,
    ):
        self._working_dir = working_dir
        self._max_lines_count = max_lines_count
        self._flow_inputs = flow_inputs
        self._default_inputs_mapping = {key: f"${{data.{key}}}" for key in flow_inputs}\
            if flow_inputs is not None else None
        self._multimedia_processor = MultimediaProcessor.create(message_format)

    def process_batch_inputs(self, input_dirs: Dict[str, str], inputs_mapping: Dict[str, str]):
        input_dicts = self._resolve_input_data_and_check(input_dirs)
        return self._validate_and_apply_inputs_mapping(input_dicts, inputs_mapping)

    def _resolve_input_data_and_check(self, input_dirs: Dict[str, str]):
        input_dicts = self._resolve_input_data(input_dirs)
        no_input_data = all(len(data) == 0 for data in input_dicts.values())
        if no_input_data:
            input_dirs_str = "\n".join(f"{input}: {Path(path).as_posix()}" for input, path in input_dirs.items())
            message_format = (
                "Couldn't find any inputs data at the given input paths. Please review the provided path "
                "and consider resubmitting.\n{input_dirs}"
            )
            raise EmptyInputsData(message_format=message_format, input_dirs=input_dirs_str)
        return input_dicts

    def process_batch_inputs_without_inputs_mapping(self, input_dirs: Dict[str, str]):
        input_dicts = self._resolve_input_data_and_check(input_dirs)
        merged_list = self._merge_input_dicts_by_line(input_dicts)
        if len(merged_list) == 0:
            raise InputMappingError(
                message_format=(
                    "The input for batch run is incorrect. Could not find one complete line on the provided input. "
                    "Please ensure that you supply data on the same line to resolve this issue."
                )
            )

        return merged_list

    def _process_batch_inputs_line(self, inputs: Dict[str, Any], inputs_mapping: Dict[str, str]):
        if not inputs_mapping:
            logger.warning(
                msg=(
                    "Starting run without column mapping may lead to unexpected results. "
                    "Please consult the following documentation for more information: https://aka.ms/pf/column-mapping"
                )
            )
        return apply_inputs_mapping(inputs, inputs_mapping)

    def _resolve_input_data(self, input_dirs: Dict[str, str]):
        """Resolve input data from input dirs"""
        result = {}
        for input_key, input_dir in input_dirs.items():
            input_dir = resolve_dir_to_absolute(self._working_dir, input_dir)
            result[input_key] = self._resolve_data_from_input_path(input_dir)
        return result

    def _resolve_data_from_input_path(self, input_path: Path):
        """Resolve input data from directory"""
        result = []
        if input_path.is_file():
            result.extend(
                self._multimedia_processor.resolve_multimedia_data_recursively(
                    input_path.parent, load_data(local_path=input_path, max_rows_count=self._max_lines_count)
                )
            )
        else:
            for input_file in input_path.rglob("*"):
                if input_file.is_file():
                    result.extend(
                        self._multimedia_processor.resolve_multimedia_data_recursively(
                            input_file.parent, load_data(local_path=input_file, max_rows_count=self._max_lines_count)
                        )
                    )
                    if self._max_lines_count and len(result) >= self._max_lines_count:
                        break
        if self._max_lines_count and len(result) >= self._max_lines_count:
            logger.warning(
                (
                    "The data provided exceeds the maximum lines limit. Currently, only the first "
                    f"{self._max_lines_count} lines are processed."
                )
            )
            return result[: self._max_lines_count]
        return result

    def _validate_and_apply_inputs_mapping(self, inputs, inputs_mapping) -> List[Dict[str, Any]]:
        """Validate and apply inputs mapping for all lines in the flow.

        :param inputs: The inputs to the flow.
        :type inputs: Any
        :param inputs_mapping: The mapping of input names to their corresponding values.
        :type inputs_mapping: Dict[str, Any]
        :return: A list of dictionaries containing the resolved inputs for each line in the flow.
        :rtype: List[Dict[str, Any]]
        """
        if not inputs_mapping:
            logger.warning(
                msg=(
                    "Starting run without column mapping may lead to unexpected results. "
                    "Please consult the following documentation for more information: https://aka.ms/pf/column-mapping"
                )
            )

        inputs_mapping = self._complete_inputs_mapping_by_default_value(inputs_mapping)
        resolved_inputs = self._apply_inputs_mapping_for_all_lines(inputs, inputs_mapping)
        return resolved_inputs

    def _complete_inputs_mapping_by_default_value(self, inputs_mapping):
        inputs_mapping = inputs_mapping or {}
        result_mapping = self._default_inputs_mapping
        # For input has default value, we don't try to read data from default mapping.
        # Default value is in higher priority than default mapping.
        for key, value in self._flow_inputs.items():
            if value and value.default is not None:
                del result_mapping[key]
        result_mapping.update(inputs_mapping)
        return result_mapping

    def _apply_inputs_mapping_for_all_lines(
        self,
        input_dict: Mapping[str, List[Mapping[str, Any]]],
        inputs_mapping: Mapping[str, str],
    ) -> List[Dict[str, Any]]:
        """Apply input mapping to all input lines.

        For example:
        input_dict = {
            'data': [{'question': 'q1', 'answer': 'ans1'}, {'question': 'q2', 'answer': 'ans2'}],
            'baseline': [{'answer': 'baseline_ans1'}, {'answer': 'baseline_ans2'}],
            'output': [{'answer': 'output_ans1', 'line_number': 0}, {'answer': 'output_ans2', 'line_number': 1}],
        }
        inputs_mapping: {
            "question": "${data.question}",  # Question from the data
            "groundtruth": "${data.answer}",  # Answer from the data
            "baseline": "${baseline.answer}",  # Answer from the baseline
            "deployment_name": "text-davinci-003",  # literal value
            "answer": "${output.answer}",  # Answer from the output
            "line_number": "${output.line_number}",  # Answer from the output
        }

        Returns:
        [{
            "question": "q1",
            "groundtruth": "ans1",
            "baseline": "baseline_ans1",
            "answer": "output_ans1",
            "deployment_name": "text-davinci-003",
            "line_number": 0,
        },
        {
            "question": "q2",
            "groundtruth": "ans2",
            "baseline": "baseline_ans2",
            "answer": "output_ans2",
            "deployment_name": "text-davinci-003",
            "line_number": 1,
        }]
        """
        if inputs_mapping is None:
            # This exception should not happen since developers need to use _default_inputs_mapping for None input.
            # So, this exception is one system error.
            raise UnexpectedError(
                message_format=(
                    "The input for batch run is incorrect. Please make sure to set up a proper input mapping before "
                    "proceeding. If you need additional help, feel free to contact support for further assistance."
                )
            )
        merged_list = self._merge_input_dicts_by_line(input_dict)
        if len(merged_list) == 0:
            raise InputMappingError(
                message_format=(
                    "The input for batch run is incorrect. Could not find one complete line on the provided input. "
                    "Please ensure that you supply data on the same line to resolve this issue."
                )
            )

        result = [apply_inputs_mapping(item, inputs_mapping) for item in merged_list]
        return result

    def _merge_input_dicts_by_line(
        self,
        input_dict: Mapping[str, List[Mapping[str, Any]]],
    ) -> List[Mapping[str, Mapping[str, Any]]]:
        for input_key, list_of_one_input in input_dict.items():
            if not list_of_one_input:
                raise InputMappingError(
                    message_format=(
                        "The input for batch run is incorrect. Input from key '{input_key}' is an empty list, "
                        "which means we cannot generate a single line input for the flow run. "
                        "Please rectify the input and try again."
                    ),
                    input_key=input_key,
                )

        # Check if line numbers are aligned.
        all_lengths_without_line_number = {
            input_key: len(list_of_one_input)
            for input_key, list_of_one_input in input_dict.items()
            if not any(LINE_NUMBER_KEY in one_item for one_item in list_of_one_input)
        }
        if len(set(all_lengths_without_line_number.values())) > 1:
            raise InputMappingError(
                message_format=(
                    "The input for batch run is incorrect. Line numbers are not aligned. "
                    "Some lists have dictionaries missing the 'line_number' key, "
                    "and the lengths of these lists are different. "
                    "List lengths are: {all_lengths_without_line_number}. "
                    "Please make sure these lists have the same length or add 'line_number' key to each dictionary."
                ),
                all_lengths_without_line_number=all_lengths_without_line_number,
            )

        # Collect each line item from each input.
        tmp_dict = {}
        for input_key, list_of_one_input in input_dict.items():
            if input_key in all_lengths_without_line_number:
                # Assume line_number start from 0.
                for index, one_line_item in enumerate(list_of_one_input):
                    if index not in tmp_dict:
                        tmp_dict[index] = {}
                    tmp_dict[index][input_key] = one_line_item
            else:
                for one_line_item in list_of_one_input:
                    if LINE_NUMBER_KEY in one_line_item:
                        index = one_line_item[LINE_NUMBER_KEY]
                        if index not in tmp_dict:
                            tmp_dict[index] = {}
                        tmp_dict[index][input_key] = one_line_item
        result = []
        for line, values_for_one_line in tmp_dict.items():
            # Missing input is not acceptable line.
            if len(values_for_one_line) != len(input_dict):
                continue
            values_for_one_line[LINE_NUMBER_KEY] = line
            result.append(values_for_one_line)
        return result
