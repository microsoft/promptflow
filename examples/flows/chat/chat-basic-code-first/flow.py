from dataclasses import dataclass
from jinja2 import Template
from pathlib import Path
from promptflow import trace, PFClient
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
    from promptflow._sdk._configuration import Configuration

    prompt = load_prompt("chat.jinja2", question, chat_history)
    config = Configuration.get_instance()
    # TODO: create your own config.json
    workspace_config = config._get_workspace_from_config(path="./config.json")
    config.set_config(Configuration.CONNECTION_PROVIDER, "azureml:" + workspace_config)
    pf = PFClient()
    connection = pf.connections.get(
        "open_ai_connection", with_secrets=True
    )  # TODO: add connection to function inputs
    output = chat(
        connection=connection,
        prompt=prompt,
        deployment_name="gpt-35-turbo",
        max_tokens=256,
        temperature=0.7,
    )
    # TODO: Result(answer=output)
    return dict(answer=output)


if __name__ == "__main__":
    from promptflow._trace._start_trace import start_trace  # TODO move to public API

    start_trace()
    
    result = flow_entry("What's Azure Machine Learning?", [])
    print(result)
