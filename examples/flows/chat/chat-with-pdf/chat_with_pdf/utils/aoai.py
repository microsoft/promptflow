from typing import List
import openai
import os
import tiktoken
from jinja2 import Template

from .retry import (
    retry_and_handle_exceptions,
    retry_and_handle_exceptions_for_generator,
)
from .logging import log


def extract_delay_from_rate_limit_error_msg(text):
    import re

    pattern = r"retry after (\d+)"
    match = re.search(pattern, text)
    if match:
        retry_time_from_message = match.group(1)
        return float(retry_time_from_message)
    else:
        return 5  # default retry time


class AOAI:
    def __init__(self):
        openai.api_type = "azure"
        openai.api_base = os.environ.get("OPENAI_API_BASE")
        openai.api_version = os.environ.get("OPENAI_API_VERSION")
        openai.api_key = os.environ.get("OPENAI_API_KEY")


class AOAIChat(AOAI):
    @retry_and_handle_exceptions(
        exception_to_check=(
            openai.error.RateLimitError,
            openai.error.APIError,
            KeyError,
        ),
        max_retries=5,
        extract_delay_from_error_message=extract_delay_from_rate_limit_error_msg,
    )
    def generate(self, messages: list, **kwargs) -> List[float]:
        return openai.ChatCompletion.create(
            engine=os.environ.get("CHAT_MODEL_DEPLOYMENT_NAME"),
            messages=messages,
            **kwargs,
        )["choices"][0]["message"]["content"]

    @retry_and_handle_exceptions_for_generator(
        exception_to_check=(
            openai.error.RateLimitError,
            openai.error.APIError,
            KeyError,
        ),
        max_retries=5,
        extract_delay_from_error_message=extract_delay_from_rate_limit_error_msg,
    )
    def stream(self, messages: list, **kwargs):
        response = openai.ChatCompletion.create(
            engine=os.environ.get("CHAT_MODEL_DEPLOYMENT_NAME"),
            messages=messages,
            stream=True,
            **kwargs,
        )

        for chunk in response:
            delta = chunk["choices"][0]["delta"]
            if "content" in delta:
                yield delta["content"]


class AOAIEmbedding(AOAI):
    @retry_and_handle_exceptions(
        exception_to_check=openai.error.RateLimitError,
        max_retries=5,
        extract_delay_from_error_message=extract_delay_from_rate_limit_error_msg,
    )
    def generate(self, text: str) -> List[float]:
        return openai.Embedding.create(
            input=text, engine=os.environ.get("EMBEDDING_MODEL_DEPLOYMENT_NAME")
        )["data"][0]["embedding"]


def count_token(text: str) -> int:
    encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def render_with_token_limit(template: Template, token_limit: int, **kwargs) -> str:
    text = template.render(**kwargs)
    token_count = count_token(text)
    if token_count > token_limit:
        message = f"token count {token_count} exceeds limit {token_limit}"
        log(message)
        raise ValueError(message)
    return text


if __name__ == "__main__":
    print(count_token("hello world, this is impressive"))
