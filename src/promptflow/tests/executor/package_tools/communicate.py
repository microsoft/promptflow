from promptflow import ToolProvider, tool
from promptflow.core._connection import AzureOpenAIConnection


class Communication(ToolProvider):
    def __init__(self, connection: AzureOpenAIConnection):
        super().__init__()
        self.connection = connection

    @tool
    def say_hello(self, connection_2: AzureOpenAIConnection):
        """say hello to the world or someone else"""
        assert isinstance(self.connection, AzureOpenAIConnection)
        assert isinstance(connection_2, AzureOpenAIConnection)
        return "Hello World!"
