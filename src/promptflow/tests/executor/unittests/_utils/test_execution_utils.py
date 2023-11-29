import pytest

from promptflow._utils.execution_utils import apply_default_value_for_input
from promptflow.contracts.flow import FlowInputDefinition
from promptflow.contracts.tool import ValueType


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
            (
                {
                    "input_from_default": FlowInputDefinition(type=ValueType.BOOL, default=False),
                },
                {},
                {"input_from_default": False},
            ),
            (
                {
                    "input_from_default": FlowInputDefinition(type=ValueType.LIST, default=[]),
                },
                {},
                {"input_from_default": []},
            ),
            (
                {
                    "input_from_default": FlowInputDefinition(type=ValueType.OBJECT, default={}),
                },
                {},
                {"input_from_default": {}},
            ),
        ],
    )
    def test_apply_default_value_for_input(self, flow_inputs, inputs, expected_inputs):
        result = apply_default_value_for_input(flow_inputs, inputs)
        assert result == expected_inputs
