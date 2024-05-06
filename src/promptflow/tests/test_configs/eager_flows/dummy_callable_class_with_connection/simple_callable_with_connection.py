from promptflow.connections import AzureOpenAIConnection


class MyFlow:
    def __init__(self, connection: AzureOpenAIConnection):
        self._connection = connection

    def __call__(self):
        assert isinstance(self._connection, AzureOpenAIConnection)
        return "Dummy output"
