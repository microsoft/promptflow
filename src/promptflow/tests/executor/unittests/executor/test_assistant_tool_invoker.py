import pytest
from pathlib import Path
from typing import Callable

from promptflow import tool
from promptflow.executor._assistant_tool_invoker import AssistantToolInvoker
from promptflow.executor._errors import UnsupportedAssistantToolType


@pytest.mark.unittest
class TestAssistantToolInvoker:
    @pytest.fixture
    def tool_definitions(self):
        return [
            {"type": "code_interpreter"},
            {"type": "retrieval"},
            {
                "type": "function",
                "tool_type": "python",
                "source": {"type": "code", "path": "test_assistant_tool_invoker.py"},
            }
        ]

    @pytest.mark.parametrize(
        "predefined_inputs", [({}), ({"input_int": 1})]
    )
    def test_load_tools(self, predefined_inputs):
        input_int = 1
        input_str = "test"
        tool_definitions = [
            {"type": "code_interpreter"},
            {"type": "retrieval"},
            {
                "type": "function",
                "tool_type": "python",
                "source": {"type": "code", "path": "test_assistant_tool_invoker.py"},
                "predefined_inputs": predefined_inputs
            }
        ]

        # Test load tools
        invoker = AssistantToolInvoker.init(tool_definitions, working_dir=Path(__file__).parent)
        for tool_name, assistant_tool in invoker._assistant_tools.items():
            assert tool_name in ("code_interpreter", "retrieval", "sample_tool")
            assert assistant_tool.name == tool_name
            assert isinstance(assistant_tool.openai_definition, dict)
            if tool_name in ("code_interpreter", "retrieval"):
                assert assistant_tool.func is None
            else:
                assert isinstance(assistant_tool.func, Callable)

        # Test to_openai_tools
        descriptions = invoker.to_openai_tools()
        assert len(descriptions) == 3
        properties = {
            "input_int": {"description": "This is a sample input int.", "type": "number"},
            "input_str": {"description": "This is a sample input str.", "type": "string"}
        }
        required = ["input_int", "input_str"]
        self._remove_predefined_inputs(properties, predefined_inputs.keys())
        self._remove_predefined_inputs(required, predefined_inputs.keys())
        for description in descriptions:
            if description["type"] in ("code_interpreter", "retrieval"):
                assert description == {"type": description["type"]}
            else:
                assert description == {
                    "type": "function",
                    "function": {
                        "name": "sample_tool",
                        "description": "This is a sample tool.",
                        "parameters": {
                            "type": "object",
                            "properties": properties,
                            "required": required
                        }
                    }
                }

        # Test invoke tool
        kwargs = {"input_int": input_int, "input_str": input_str}
        self._remove_predefined_inputs(kwargs, predefined_inputs.keys())
        result = invoker.invoke_tool(func_name="sample_tool", kwargs=kwargs)
        assert result == (input_int, input_str)

    def test_load_tools_with_invalid_case(self):
        tool_definitions = [{"type": "invalid_type"}]
        with pytest.raises(UnsupportedAssistantToolType) as exc_info:
            AssistantToolInvoker.init(tool_definitions)
        assert "Unsupported assistant tool type" in exc_info.value.message

    def _remove_predefined_inputs(self, value: any, predefined_inputs: list):
        for input in predefined_inputs:
            if input in value:
                if isinstance(value, dict):
                    value.pop(input)
                elif isinstance(value, list):
                    value.remove(input)


@tool
def sample_tool(input_int: int, input_str: str):
    """This is a sample tool.

    :param input_int: This is a sample input int.
    :type input_int: int
    :param input_str: This is a sample input str.
    :type input_str: str
    """

    return input_int, input_str
