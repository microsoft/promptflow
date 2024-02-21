import json
import os
from pathlib import Path

from dotenv import load_dotenv
from jinja2 import Template

from promptflow import trace
from promptflow._sdk.entities import AzureOpenAIConnection
from promptflow.tools.aoai import chat

BASE_DIR = Path(__file__).absolute().parent


@trace
def load_prompt(jinja2_template: str, answer: str, statement: str, examples: list) -> str:
    """Load prompt function."""
    with open(BASE_DIR / jinja2_template, "r", encoding="utf-8") as f:
        tmpl = Template(f.read(), trim_blocks=True, keep_trailing_newline=True)
        prompt = tmpl.render(answer=answer, statement=statement, examples=examples)
        return prompt


@trace
def check_list(answer: str, statements: dict):
    """Check the answer applies for a collection of check statement."""
    if isinstance(statements, str):
        statements = json.loads(statements)

    results = {}
    for key, statement in statements.items():
        r = check(answer=answer, statement=statement)
        results[key] = r
    return results


@trace
def check(answer: str, statement: str):
    """Check the answer applies for the check statement."""
    examples = [
        {
            "answer": "ChatGPT is a conversational AI model developed by OpenAI.",
            "statement": "It contains a brief explanation of ChatGPT.",
            "score": 5,
            "explanation": "The statement is correct. The answer contains a brief explanation of ChatGPT.",
        }
    ]

    prompt = load_prompt("prompt.md", answer, statement, examples)

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
    output = json.loads(output)
    return output


if __name__ == "__main__":
    from promptflow import start_trace

    start_trace()

    answer = """ChatGPT is a conversational AI model developed by OpenAI.
    It is based on the GPT-3 architecture and is designed to generate human-like responses to text inputs.
    ChatGPT is capable of understanding and responding to a wide range of topics and can be used for tasks such as
    answering questions, generating creative content, and providing assistance with various tasks.
    The model has been trained on a diverse range of internet text and is constantly being updated to improve its
    performance and capabilities. ChatGPT is available through the OpenAI API and can be accessed by developers and
    researchers to build applications and tools that leverage its capabilities."""
    statements = {
        "correctness": "It contains a detailed explanation of ChatGPT.",
        "consise": "It is a consise statement.",
    }

    result = check_list(
        answer=answer,
        statements=statements,
    )
    print(result)
