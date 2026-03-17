import os
from pathlib import Path

from promptflow.tracing import trace
from promptflow.core import OpenAIModelConfiguration, Prompty

BASE_DIR = Path(__file__).absolute().parent

# MiniMax API base URL (OpenAI-compatible)
MINIMAX_BASE_URL = "https://api.minimax.io/v1"

# Available MiniMax models
MINIMAX_MODELS = {
    "MiniMax-M2.5": "General-purpose model with 204K context window",
    "MiniMax-M2.5-highspeed": "Faster variant optimized for lower latency",
}


def _clamp_temperature(temperature: float) -> float:
    """Clamp temperature to MiniMax's accepted range [0.0, 1.0]."""
    return max(0.0, min(1.0, temperature))


class ChatFlow:
    """A chat flow powered by MiniMax's LLM via the OpenAI-compatible API.

    MiniMax provides an OpenAI-compatible API endpoint, so it works seamlessly
    with prompt flow's OpenAI connection type by setting the base_url.
    """

    def __init__(
        self,
        model_config: OpenAIModelConfiguration,
        max_total_token: int = 4096,
    ):
        self.model_config = model_config
        self.max_total_token = max_total_token

    @trace
    def __call__(
        self,
        question: str = "What is Prompt flow?",
        chat_history: list = None,
    ) -> str:
        """Flow entry function."""
        prompty = Prompty.load(
            source=BASE_DIR / "chat.prompty",
            model={"configuration": self.model_config},
        )

        chat_history = chat_history or []
        while len(chat_history) > 0:
            token_count = prompty.estimate_token_count(
                question=question, chat_history=chat_history
            )
            if token_count > self.max_total_token:
                chat_history = chat_history[1:]
            else:
                break

        output = prompty(question=question, chat_history=chat_history)
        return output


def get_minimax_config(
    model: str = "MiniMax-M2.5",
    api_key: str = None,
) -> OpenAIModelConfiguration:
    """Create an OpenAIModelConfiguration pre-configured for MiniMax.

    Args:
        model: MiniMax model name. Options: MiniMax-M2.5, MiniMax-M2.5-highspeed.
        api_key: MiniMax API key. Falls back to MINIMAX_API_KEY env var.

    Returns:
        OpenAIModelConfiguration configured for MiniMax.
    """
    api_key = api_key or os.environ.get("MINIMAX_API_KEY")
    if not api_key:
        raise ValueError(
            "MiniMax API key is required. Set MINIMAX_API_KEY environment variable "
            "or pass api_key parameter."
        )
    return OpenAIModelConfiguration(
        model=model,
        base_url=MINIMAX_BASE_URL,
        api_key=api_key,
    )


if __name__ == "__main__":
    from promptflow.tracing import start_trace

    start_trace()
    config = get_minimax_config(model="MiniMax-M2.5")
    flow = ChatFlow(config)
    result = flow("What is Prompt flow?", [])
    print(result)
