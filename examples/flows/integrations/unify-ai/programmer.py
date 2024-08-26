from pathlib import Path
from typing import TypedDict

from jinja2 import Template
from llm import my_llm_tool

from promptflow.tracing import trace

BASE_DIR = Path(__file__).absolute().parent


class Result(TypedDict):
    output: str


@trace
def load_prompt(jinja2_template: str, text: str) -> str:
    """Load prompt function."""
    with open(BASE_DIR / jinja2_template, "r", encoding="utf-8") as f:
        prompt = Template(
            f.read(), trim_blocks=True, keep_trailing_newline=True
        ).render(text=text)
        return prompt


@trace
def write_simple_program(
    text: str = "Hello World!",
    model_name="llama-3.1-8b-chat",
    provider_name="together-ai",
) -> Result:
    """Ask LLM to write a simple program."""
    prompt = load_prompt("hello.jinja2", text)
    output = my_llm_tool(
        prompt=prompt,
        model_name=model_name,
        provider_name=provider_name,
        max_tokens=120,
    )
    return Result(output=output)


if __name__ == "__main__":
    from promptflow.tracing import start_trace

    start_trace()
    result = write_simple_program("Hello, world!")
    print(result)
