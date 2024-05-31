import json
import os

from dotenv import load_dotenv
from pathlib import Path
from typing import TypedDict

from promptflow.tracing import trace
from promptflow.core import Prompty

BASE_DIR = Path(__file__).absolute().parent


class WeatherInfo(TypedDict):
    location: str
    temperature: float
    format: str
    forecast: list[str]
    num_days: int


def get_current_weather(location, format="fahrenheit"):
    """Get the current weather in a given location"""
    return WeatherInfo(
        location=location, temperature="72", format=format, forecast=["sunny", "windy"]
    )


def get_n_day_weather_forecast(location, format, num_days):
    """Get next num_days weather in a given location"""
    return WeatherInfo(
        location=location,
        temperature="60",
        format=format,
        forecast=["rainy"],
        num_days=num_days,
    )


@trace
def run_function(response_message: dict) -> str:
    if "tool_calls" in response_message and len(response_message["tool_calls"]) == 1:
        call = response_message["tool_calls"][0]
        function = call["function"]
        function_name = function["name"]
        function_args = json.loads(function["arguments"])
        print(function_args)
        result = globals()[function_name](**function_args)
        return str(result)

    print("No function call")
    if isinstance(response_message, dict):
        result = response_message["content"]
    else:
        result = response_message
    return result


MAX_TOTAL_TOKEN = 2048


@trace
def chat(
    question: str = "What's the weather of Beijing?",
    chat_history: list = None,
    max_total_token=2048,
) -> str:
    """Flow entry function."""

    if "OPENAI_API_KEY" not in os.environ and "AZURE_OPENAI_API_KEY" not in os.environ:
        # load environment variables from .env file
        load_dotenv()

    prompty = Prompty.load(source=BASE_DIR / "chat_with_tools.prompty")

    chat_history = chat_history or []
    # Try to render the prompt with token limit and reduce the history count if it fails
    while len(chat_history) > 0:
        token_count = prompty.estimate_token_count(
            question=question, chat_history=chat_history
        )
        if token_count > MAX_TOTAL_TOKEN:
            chat_history = chat_history[1:]
            print(
                f"Reducing chat history count to {len(chat_history)} to fit token limit"
            )
        else:
            break

    output = prompty(question=question, chat_history=chat_history)

    function_output = run_function(output)

    return function_output


if __name__ == "__main__":
    from promptflow.tracing import start_trace

    start_trace()

    result = chat("What's the weather of Beijing?")
    print(result)
