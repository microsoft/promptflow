from promptflow._sdk.entities import AzureOpenAIConnection


class Hello:
    def __init__(self, connection: AzureOpenAIConnection) -> None:
        self.connection = connection

    def __call__(self, text: str) -> str:
        return f"Hello {self.connection.name} {text}!"
