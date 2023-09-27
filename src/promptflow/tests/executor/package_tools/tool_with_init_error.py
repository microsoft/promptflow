from promptflow import ToolProvider, tool


class TestLoadErrorTool(ToolProvider):
    def __init__(self):
        raise Exception("Tool load error.")

    @tool
    def tool(self, name: str):
        return name
