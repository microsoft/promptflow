from typing import Any

import pytest

from promptflow._core._errors import NotSupported
from promptflow.contracts.flow import InputAssignment
from promptflow.executor._errors import InputNotFound, InputNotFoundFromAncestorNodeOutput, UnsupportedReference
from promptflow.executor._input_assignment_parser import parse_node_property, parse_value

FLOW_INPUTS = {"text": "hello promptflow"}
NODE_OUTPUTS = {"node1": "hello promptflow"}


class WrongInputAssignment:
    value: Any
    value_type: str = "wrong_type"
    section: str = ""
    property: str = ""


@pytest.mark.unittest
class TestInputAssignmentParser:
    @pytest.mark.parametrize(
        "input, expected_value",
        [
            ("hello promptflow", "hello promptflow"),
            ("${inputs.text}", "hello promptflow"),
            ("${node1.output}", "hello promptflow"),
        ],
    )
    def test_parse_value(self, input, expected_value):
        input_assignment = InputAssignment.deserialize(input)
        actual_value = parse_value(input_assignment, NODE_OUTPUTS, FLOW_INPUTS)
        assert actual_value == expected_value

    @pytest.mark.parametrize(
        "input, expected_error_class, expected_error_message",
        [
            (
                "${inputs.word}",
                InputNotFound,
                (
                    "The input 'word' is not found from flow inputs 'text'. "
                    "Please check the input name and try again."
                ),
            ),
            (
                "${node2.output}",
                InputNotFoundFromAncestorNodeOutput,
                (
                    "The input 'node2' is not found from ancestor node outputs 'node1'. "
                    "Please check the node name and try again."
                ),
            ),
            (
                "${node1.word}",
                UnsupportedReference,
                (
                    "The section 'word' of reference is currently unsupported. "
                    "Please specify the output part of the node 'node1'."
                ),
            ),
            (
                WrongInputAssignment(),
                NotSupported,
                (
                    "The type 'wrong_type' is currently unsupported. "
                    "Please choose from available types: 'LITERAL', 'FLOW_INPUT' and try again."
                ),
            ),
        ],
    )
    def test_parse_value_with_exception(self, input, expected_error_class, expected_error_message):
        input_assignment = InputAssignment.deserialize(input) if isinstance(input, str) else input
        with pytest.raises(expected_error_class) as exc_info:
            parse_value(input_assignment, NODE_OUTPUTS, FLOW_INPUTS)
            assert exc_info.value.message == expected_error_message

    @pytest.mark.parametrize(
        "node_name, node_val, property, expected_value",
        [],
    )
    def test_parse_node_property(self, node_name, node_val, property, expected_value):
        actual_value = parse_node_property(node_name, node_val, property)
        assert actual_value == expected_value

    @pytest.mark.parametrize(
        "node_name, node_val, property, expected_error_class, expected_error_message",
        [],
    )
    def test_parse_node_property_with_exception(
        self, node_name, node_val, property, expected_error_class, expected_error_message
    ):
        with pytest.raises(expected_error_class) as exc_info:
            parse_node_property(node_name, node_val, property)
            assert exc_info.value.message == expected_error_message
