import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from jinja2 import Template

from promptflow.tracing import trace
from promptflow.connections import AzureOpenAIConnection
from promptflow.tools.aoai import chat

BASE_DIR = Path(__file__).absolute().parent


@trace
def load_prompt(jinja2_template: str, question: str, chat_history: list) -> str:
    """Load prompt function."""
    with open(BASE_DIR / jinja2_template, "r", encoding="utf-8") as f:
        tmpl = Template(f.read(), trim_blocks=True, keep_trailing_newline=True)
        prompt = tmpl.render(question=question, chat_history=chat_history)
        return prompt


@dataclass
class Result:
    answer: str


@trace
def flow_entry(question: str = "What is ChatGPT?", chat_history: list = []) -> Result:
    """Flow entry function."""

    prompt = load_prompt("chat.jinja2", question, chat_history)
    if "OPENAI_API_KEY" not in os.environ:
        # load environment variables from .env file
        load_dotenv()

    if "OPENAI_API_KEY" not in os.environ:
        raise Exception("Please specify environment variables: OPENAI_API_KEY")

    connection = AzureOpenAIConnection(
        api_key=os.environ["OPENAI_API_KEY"],
        api_base=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_version=os.environ.get("OPENAI_API_VERSION", "2023-07-01-preview"),
    )

    output = chat(
        connection=connection,
        prompt=prompt,
        deployment_name="gpt-35-turbo",
        max_tokens=256,
        temperature=0.7,
    )
    return Result(answer=output)


if __name__ == "__main__":
    from promptflow.tracing import start_trace

    start_trace()

    result = flow_entry("What's Azure Machine Learning?", [])
    print(result)
