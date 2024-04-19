import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from jinja2 import Template
from openai import AzureOpenAI

from promptflow.tracing import trace
from promptflow.core import AzureOpenAIModelConfiguration


BASE_DIR = Path(__file__).absolute().parent


@trace
def load_prompt(jinja2_template: str, code: str, examples: list) -> str:
    """Load prompt function."""
    with open(BASE_DIR / jinja2_template, "r", encoding="utf-8") as f:
        tmpl = Template(f.read(), trim_blocks=True, keep_trailing_newline=True)
        prompt = tmpl.render(code=code, examples=examples)
        return prompt


@dataclass
class Result:
    correctness: float
    readability: float
    explanation: str


class CodeEvaluator:
    def __init__(self, model_config: AzureOpenAIModelConfiguration):
        self.model_config = model_config
        self.client = AzureOpenAI(
            azure_endpoint=model_config.azure_endpoint,
            api_version=model_config.api_version,
            api_key=model_config.api_key,
        )

    def __call__(self, code: str) -> Result:
        """Evaluate the code based on correctness, readability."""
        examples = [
            {
                "code": 'print("Hello, world!")',
                "correctness": 5,
                "readability": 5,
                "explanation": "The code is correct as it is a simple question and answer format. "
                "The readability is also good as the code is short and easy to understand.",
            }
        ]

        prompt = load_prompt("prompt.md", code, examples)
        messages = [{"content": prompt, "role": "system"}]
        response = self.client.chat.completions.create(
            model=self.model_config.azure_deployment,
            messages=messages,
            temperature=2,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
            stop=None,
            n=1,
        )

        output = response.choices[0].message.content
        print(output)
        output = Result(**json.loads(output))
        return output


if __name__ == "__main__":
    from promptflow.tracing import start_trace
    from promptflow.client import PFClient

    start_trace()
    if "AZURE_OPENAI_API_KEY" not in os.environ:
        # load environment variables from .env file
        load_dotenv()

    if "AZURE_OPENAI_API_KEY" not in os.environ:
        raise Exception("Please specify environment variables: AZURE_OPENAI_API_KEY")
    model_config = AzureOpenAIModelConfiguration(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"], 
        azure_deployment="gpt-35-turbo",
    )
    evaluator = CodeEvaluator(model_config)
    result = evaluator('print("Hello, world!")')
    print(result)
