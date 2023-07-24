from promptflow import ToolProvider, tool
from promptflow.core.tools_manager import register_builtins
from promptflow.connections import CustomConnection


class MyBuiltin(ToolProvider):
    def __init__(self, my_connection: CustomConnection):
        super().__init__()
        self.connection = my_connection

    @tool
    def show(self):
        return self.connection


register_builtins(MyBuiltin)
