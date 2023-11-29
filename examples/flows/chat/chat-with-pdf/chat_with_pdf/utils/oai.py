from typing import List
import openai
from openai.version import VERSION as OPENAI_VERSION
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
        if OPENAI_VERSION.startswith("0."):
            raise Exception(
                "Please upgrade your OpenAI package to version >= 1.0.0 or "
                "using the command: pip install --upgrade openai."
            )
        init_params = {}
        api_type = os.environ.get("OPENAI_API_TYPE")
        if os.getenv("OPENAI_API_VERSION") is not None:
            init_params["api_version"] = os.environ.get("OPENAI_API_VERSION")
        if os.getenv("OPENAI_ORG_ID") is not None:
            init_params["organization"] = os.environ.get("OPENAI_ORG_ID")
        if os.getenv("OPENAI_API_KEY") is None:
            raise ValueError("OPENAI_API_KEY is not set in environment variables")
        if os.getenv("OPENAI_API_BASE") is not None:
            if api_type == "azure":
                init_params["azure_endpoint"] = os.environ.get("OPENAI_API_BASE")
            else:
                init_params["base_url"] = os.environ.get("OPENAI_API_BASE")

        init_params["api_key"] = os.environ.get("OPENAI_API_KEY")

        # A few sanity checks
        if api_type == "azure":
            if init_params.get("azure_endpoint") is None:
                raise ValueError(
                    "OPENAI_API_BASE is not set in environment variables, this is required when api_type==azure"
                )
            if init_params.get("api_version") is None:
                raise ValueError(
                    "OPENAI_API_VERSION is not set in environment variables, this is required when api_type==azure"
                )
            if init_params["api_key"].startswith("sk-"):
                raise ValueError(
                    "OPENAI_API_KEY should not start with sk- when api_type==azure, "
                    "are you using openai key by mistake?"
                )
            from openai import AzureOpenAI as Client
        else:
            from openai import OpenAI as Client
        self.client = Client(**init_params)


class OAIChat(OAI):
    @retry_and_handle_exceptions(
        exception_to_check=(
            openai.RateLimitError,
            openai.APIStatusError,
            openai.APIConnectionError,
            KeyError,
        ),
        max_retries=5,
        extract_delay_from_error_message=extract_delay_from_rate_limit_error_msg,
    )
    def generate(self, messages: list, **kwargs) -> List[float]:
        # chat api may return message with no content.
        message = self.client.chat.completions.create(
            model=os.environ.get("CHAT_MODEL_DEPLOYMENT_NAME"),
            messages=messages,
            **kwargs,
        ).choices[0].message
        return getattr(message, "content", "")

    @retry_and_handle_exceptions_for_generator(
        exception_to_check=(
            openai.RateLimitError,
            openai.APIStatusError,
            openai.APIConnectionError,
            KeyError,
        ),
        max_retries=5,
        extract_delay_from_error_message=extract_delay_from_rate_limit_error_msg,
    )
    def stream(self, messages: list, **kwargs):
        response = self.client.chat.completions.create(
            model=os.environ.get("CHAT_MODEL_DEPLOYMENT_NAME"),
            messages=messages,
            stream=True,
            **kwargs,
        )

        for chunk in response:
            if not chunk.choices:
                continue
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
            else:
                yield ""


class OAIEmbedding(OAI):
    @retry_and_handle_exceptions(
        exception_to_check=openai.RateLimitError,
        max_retries=5,
        extract_delay_from_error_message=extract_delay_from_rate_limit_error_msg,
    )
    def generate(self, text: str) -> List[float]:
        return self.client.embeddings.create(
            input=text, model=os.environ.get("EMBEDDING_MODEL_DEPLOYMENT_NAME")
        ).data[0].embedding


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
