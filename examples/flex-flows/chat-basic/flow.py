import os

from pathlib import Path

from promptflow.tracing import trace
from promptflow.core import AzureOpenAIModelConfiguration, Prompty

BASE_DIR = Path(__file__).absolute().parent


def log(message: str):
    verbose = os.environ.get("VERBOSE", "false")
    if verbose.lower() == "true":
        print(message, flush=True)


class ChatFlow:
    def __init__(
        self, model_config: AzureOpenAIModelConfiguration, max_total_token=4096
    ):
        self.model_config = model_config
        self.max_total_token = max_total_token

    @trace
    def __call__(
        self,
        question: str = "What's Azure Machine Learning?",
        chat_history: list = None,
    ) -> str:
        """Flow entry function."""

        prompty = Prompty.load(
            source=BASE_DIR / "chat.prompty",
            model={"configuration": self.model_config},
        )

        chat_history = chat_history or []
        # Try to render the prompt with token limit and reduce the history count if it fails
        while len(chat_history) > 0:
            token_count = prompty.estimate_token_count(
                question=question, chat_history=chat_history
            )
            if token_count > self.max_total_token:
                chat_history = chat_history[1:]
                log(
                    f"Reducing chat history count to {len(chat_history)} to fit token limit"
                )
            else:
                break

        # output is a string
        output = prompty(question=question, chat_history=chat_history)

        return output


if __name__ == "__main__":
    from promptflow.tracing import start_trace

    start_trace()
    config = AzureOpenAIModelConfiguration(
        connection="open_ai_connection", azure_deployment="gpt-4o"
    )
    flow = ChatFlow(config)
    result = flow("What's Azure Machine Learning?", [])
    print(result)
