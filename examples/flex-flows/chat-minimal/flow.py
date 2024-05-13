import os

from dotenv import load_dotenv
from pathlib import Path
from promptflow.tracing import trace
from promptflow.core import Prompty

BASE_DIR = Path(__file__).absolute().parent


@trace
def chat(question: str = "What's the capital of France?") -> str:
    """Flow entry function."""

    if "OPENAI_API_KEY" not in os.environ and "AZURE_OPENAI_API_KEY" not in os.environ:
        # load environment variables from .env file
        load_dotenv()

    prompty = Prompty.load(source=BASE_DIR / "chat.prompty")
    output = prompty(question=question)
    return output


if __name__ == "__main__":
    from promptflow.tracing import start_trace

    start_trace()

    result = chat("What's the capital of France?")
    print(result)
