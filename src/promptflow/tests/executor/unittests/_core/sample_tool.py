from promptflow import tool


# This tool is for testing tools_manager.ToolsLoader.load_tool_for_script_node
@tool
def sample_tool(input: str):
    return input
