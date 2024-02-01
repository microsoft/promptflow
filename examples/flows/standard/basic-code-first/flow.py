from pathlib import Path

from jinja2 import Template
from llm import my_llm_tool

from promptflow import trace

BASE_DIR = Path(__file__).absolute().parent


@trace
def load_prompt(jinja2_template: str, text: str) -> str:
    """Load prompt function."""
    with open(BASE_DIR / jinja2_template, "r", encoding="utf-8") as f:
        prompt = Template(f.read(), trim_blocks=True, keep_trailing_newline=True).render(text=text)
        return prompt


@trace
def flow_entry(text: str = "Hello World!") -> str:
    """Flow entry function."""
    prompt = load_prompt("hello.jinja2", text)
    output = my_llm_tool(prompt=prompt, deployment_name="text-davinci-003", max_tokens=120)
    return output


if __name__ == "__main__":
    from promptflow._trace._start_trace import start_trace  # TODO move to public API

    start_trace()

    result = flow_entry("Hello, world!")
    print(result)
