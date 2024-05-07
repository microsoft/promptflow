from dataclasses import dataclass
from pathlib import Path

from promptflow.tracing import trace
from promptflow.core import AzureOpenAIModelConfiguration, Prompty

BASE_DIR = Path(__file__).absolute().parent


@dataclass
class Result:
    answer: str


class ChatFlow:
    def __init__(self, model_config: AzureOpenAIModelConfiguration):
        self.model_config = model_config

    @trace
    def __call__(
        self, question: str = "What is ChatGPT?", chat_history: list = None
    ) -> Result:
        """Flow entry function."""

        chat_history = chat_history or []

        prompty = Prompty.load(
            source=BASE_DIR / "chat.prompty",
            model={"configuration": self.model_config},
        )

        # output is a string
        output = prompty(question=question, chat_history=chat_history)

        return Result(answer=output)


if __name__ == "__main__":
    from promptflow.tracing import start_trace

    start_trace()
    config = AzureOpenAIModelConfiguration(
        connection="open_ai_connection", azure_deployment="gpt-35-turbo"
    )
    flow = ChatFlow(config)
    result = flow("What's Azure Machine Learning?", [])
    print(result)
