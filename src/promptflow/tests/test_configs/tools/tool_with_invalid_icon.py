from promptflow._core.tool import tool


@tool(name="invalid_tool_icon", icon="mock_icon_path", icon_dark="mock_icon_path", icon_light="mock_icon_path")
def invalid_tool_icon(input1: str) -> str:
    return 'hello ' + input1
