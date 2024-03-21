import inspect

import pytest

from promptflow import tool
from promptflow._core.tool import InputSetting, ToolType
from promptflow.exceptions import UserErrorException
from promptflow.tracing._tracer import Tracer
from promptflow.tracing.contracts.trace import TraceType


@tool
def decorated_without_parentheses(a: int):
    return a


@tool()
def decorated_with_parentheses(a: int):
    return a


@tool
async def decorated_without_parentheses_async(a: int):
    return a


@tool()
async def decorated_with_parentheses_async(a: int):
    return a


@tool(
    name="tool_with_attributes",
    description="Sample tool with a lot of attributes",
    type=ToolType.LLM,
    input_settings=InputSetting(),
    streaming_option_parameter="stream",
    extra_a="a",
    extra_b="b",
)
def tool_with_attributes(stream: bool, a: int, b: int):
    return stream, a, b


@pytest.mark.unittest
class TestTool:
    """This class tests the `tool` decorator."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "func",
        [
            decorated_with_parentheses,
            decorated_without_parentheses,
            decorated_with_parentheses_async,
            decorated_without_parentheses_async,
        ],
    )
    async def test_traces_are_created_correctly(self, func):
        Tracer.start_tracing("test_run_id")
        if inspect.iscoroutinefunction(func):
            result = await func(1)
        else:
            result = func(1)
        assert result == 1
        traces = Tracer.end_tracing()
        assert len(traces) == 1
        trace = traces[0]
        assert trace["name"] == func.__qualname__
        assert trace["type"] == TraceType.FUNCTION
        assert trace["inputs"] == {"a": 1}
        assert trace["output"] == 1
        assert trace["error"] is None
        assert trace["children"] == []
        assert isinstance(trace["start_time"], float)
        assert isinstance(trace["end_time"], float)

    def test_attributes_are_set_to_the_tool_function(self):
        stream, a, b = tool_with_attributes(True, 1, 2)
        # Check the results are as expected
        assert stream is True
        assert a == 1
        assert b == 2

        # Check the attributes are set to the function
        assert getattr(tool_with_attributes, "__tool") is None
        assert getattr(tool_with_attributes, "__name") == "tool_with_attributes"
        assert getattr(tool_with_attributes, "__description") == "Sample tool with a lot of attributes"
        assert getattr(tool_with_attributes, "__type") == ToolType.LLM
        assert getattr(tool_with_attributes, "__input_settings") == InputSetting()
        assert getattr(tool_with_attributes, "__extra_info") == {"extra_a": "a", "extra_b": "b"}
        assert getattr(tool_with_attributes, "_streaming_option_parameter") == "stream"

    def test_invalid_tool_type_should_raise_error(self):
        with pytest.raises(UserErrorException, match="Tool type invalid_type is not supported yet."):

            @tool(type="invalid_type")
            def invalid_tool_type():
                pass
