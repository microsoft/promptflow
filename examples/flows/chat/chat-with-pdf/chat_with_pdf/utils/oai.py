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


class OAI:
    def __init__(self):
        if os.getenv("OPENAI_API_TYPE") is not None:
            openai.api_type = os.getenv("OPENAI_API_TYPE")
        if os.getenv("OPENAI_API_BASE") is not None:
            openai.api_base = os.environ.get("OPENAI_API_BASE")
        if os.getenv("OPENAI_API_VERSION") is not None:
            openai.api_version = os.environ.get("OPENAI_API_VERSION")
        if os.getenv("OPENAI_ORG_ID") is not None:
            openai.organization = os.environ.get("OPENAI_ORG_ID")
        if os.getenv("OPENAI_API_KEY") is None:
            raise ValueError("OPENAI_API_KEY is not set in environment variables")

        openai.api_key = os.environ.get("OPENAI_API_KEY")

        # A few sanity checks
        if openai.api_type == "azure" and openai.api_base is None:
            raise ValueError(
                "OPENAI_API_BASE is not set in environment variables, this is required when api_type==azure"
            )
        if openai.api_type == "azure" and openai.api_version is None:
            raise ValueError(
                "OPENAI_API_VERSION is not set in environment variables, this is required when api_type==azure"
            )
        if openai.api_type == "azure" and openai.api_key.startswith("sk-"):
            raise ValueError(
                "OPENAI_API_KEY should not start with sk- when api_type==azure, are you using openai key by mistake?"
            )


class OAIChat(OAI):
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
        if openai.api_type == "azure":
            return openai.ChatCompletion.create(
                engine=os.environ.get("CHAT_MODEL_DEPLOYMENT_NAME"),
                messages=messages,
                **kwargs,
            )["choices"][0]["message"]["content"]
        else:
            return openai.ChatCompletion.create(
                model=os.environ.get("CHAT_MODEL_DEPLOYMENT_NAME"),
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
        if openai.api_type == "azure":
            response = openai.ChatCompletion.create(
                engine=os.environ.get("CHAT_MODEL_DEPLOYMENT_NAME"),
                messages=messages,
                stream=True,
                **kwargs,
            )
        else:
            response = openai.ChatCompletion.create(
                model=os.environ.get("CHAT_MODEL_DEPLOYMENT_NAME"),
                messages=messages,
                stream=True,
                **kwargs,
            )

        for chunk in response:
            if "choices" not in chunk or len(chunk["choices"]) == 0:
                continue
            delta = chunk["choices"][0]["delta"]
            if "content" in delta:
                yield delta["content"]


class OAIEmbedding(OAI):
    @retry_and_handle_exceptions(
        exception_to_check=openai.error.RateLimitError,
        max_retries=5,
        extract_delay_from_error_message=extract_delay_from_rate_limit_error_msg,
    )
    def generate(self, text: str) -> List[float]:
        if openai.api_type == "azure":
            return openai.Embedding.create(
                input=text, engine=os.environ.get("EMBEDDING_MODEL_DEPLOYMENT_NAME")
            )["data"][0]["embedding"]
        else:
            return openai.Embedding.create(
                input=text, model=os.environ.get("EMBEDDING_MODEL_DEPLOYMENT_NAME")
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
