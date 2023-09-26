from promptflow import ToolProvider, tool


class ScriptToolWithInit(ToolProvider):
    def __init__(self, init_input: str):
        super().__init__()
        self.init_input = init_input

    @tool
    def call(self, input: str):
        return str.join(" ", [self.init_input, input])
