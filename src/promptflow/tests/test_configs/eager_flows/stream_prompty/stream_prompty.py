from pathlib import Path

from promptflow.tracing import trace
from promptflow.core import AzureOpenAIModelConfiguration, Prompty

BASE_DIR = Path(__file__).absolute().parent


class ChatFlow:
    def __init__(self, model_config: AzureOpenAIModelConfiguration):
        self.model_config = model_config

    @trace
    def __call__(
        self, question: str = "What is ChatGPT?", chat_history: list = None
    ) -> str:
        """Flow entry function."""

        raise Exception("Exception")


if __name__ == "__main__":
    from promptflow.tracing import start_trace

    start_trace()
    config = AzureOpenAIModelConfiguration(
        connection="open_ai_connection", azure_deployment="gpt-35-turbo"
    )
    flow = ChatFlow(model_config=config)
    result = flow("What's Azure Machine Learning?", [])

    # print result in stream manner
    for r in result:
        print(result, end="")
