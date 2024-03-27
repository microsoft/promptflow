# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import re
from typing import Any, Dict, Mapping

from promptflow._constants import LINE_NUMBER_KEY
from promptflow._utils._errors import ApplyInputMappingError
from promptflow._utils.logger_utils import LoggerFactory

logger = LoggerFactory.get_logger(name=__name__)


def apply_inputs_mapping(
    inputs: Mapping[str, Mapping[str, Any]],
    inputs_mapping: Mapping[str, str],
) -> Dict[str, Any]:
    """Apply input mapping to inputs for new contract.

    .. admonition:: Examples

        .. code-block:: python

            inputs: {
                "data": {"answer": "I'm fine, thank you.", "question": "How are you?"},
                "baseline": {"answer": "The weather is good."},
            }
            inputs_mapping: {
                "question": "${data.question}",
                "groundtruth": "${data.answer}",
                "baseline": "${baseline.answer}",
                "deployment_name": "literal_value",
            }

            Returns: {
                "question": "How are you?",
                "groundtruth": "I'm fine, thank you."
                "baseline": "The weather is good.",
                "deployment_name": "literal_value",
            }

    :param inputs: A mapping of input keys to their corresponding values.
    :type inputs: Mapping[str, Mapping[str, Any]]
    :param inputs_mapping: A mapping of input keys to their corresponding mapping expressions.
    :type inputs_mapping: Mapping[str, str]
    :return: A dictionary of input keys to their corresponding mapped values.
    :rtype: Dict[str, Any]
    :raises InputMappingError: If any of the input mapping relations are not found in the inputs.
    """
    result = {}
    notfound_mapping_relations = []
    for map_to_key, map_value in inputs_mapping.items():
        # Ignore reserved key configuration from input mapping.
        if map_to_key == LINE_NUMBER_KEY:
            continue
        if not isinstance(map_value, str):  # All non-string values are literal values.
            result[map_to_key] = map_value
            continue
        match = re.search(r"^\${([^{}]+)}$", map_value)
        if match is not None:
            pattern = match.group(1)
            # Could also try each pair of key value from inputs to match the pattern.
            # But split pattern by '.' is one deterministic way.
            # So, give key with less '.' higher priority.
            splitted_str = pattern.split(".")
            find_match = False
            for i in range(1, len(splitted_str)):
                key = ".".join(splitted_str[:i])
                source = ".".join(splitted_str[i:])
                if key in inputs and source in inputs[key]:
                    find_match = True
                    result[map_to_key] = inputs[key][source]
                    break
            if not find_match:
                notfound_mapping_relations.append(map_value)
        else:
            result[map_to_key] = map_value  # Literal value
    # Return all not found mapping relations in one exception to provide better debug experience.
    if notfound_mapping_relations:
        invalid_relations = ", ".join(notfound_mapping_relations)
        raise ApplyInputMappingError(
            message_format=(
                "The input for batch run is incorrect. Couldn't find these mapping relations: {invalid_relations}. "
                "Please make sure your input mapping keys and values match your YAML input section and input data. "
                "For more information, refer to the following documentation: https://aka.ms/pf/column-mapping"
            ),
            invalid_relations=invalid_relations,
        )
    # For PRS scenario, apply_inputs_mapping will be used for exec_line and line_number is not necessary.
    if LINE_NUMBER_KEY in inputs:
        result[LINE_NUMBER_KEY] = inputs[LINE_NUMBER_KEY]
    return result
