import json

from typing import TypedDict
from pathlib import Path

from jinja2 import Template

from promptflow.tracing import trace
from promptflow.core import AzureOpenAIModelConfiguration
from promptflow.core._flow import Prompty

BASE_DIR = Path(__file__).absolute().parent


@trace
def load_prompt(jinja2_template: str, code: str, examples: list) -> str:
    """Load prompt function."""
    with open(BASE_DIR / jinja2_template, "r", encoding="utf-8") as f:
        tmpl = Template(f.read(), trim_blocks=True, keep_trailing_newline=True)
        prompt = tmpl.render(code=code, examples=examples)
        return prompt


class Result(TypedDict):
    correctness: float
    readability: float
    explanation: str


class CodeEvaluator:
    def __init__(self, model_config: AzureOpenAIModelConfiguration):
        self.model_config = model_config

    def __call__(self, code: str) -> Result:
        """Evaluate the code based on correctness, readability."""
        prompty = Prompty.load(
            source=BASE_DIR / "eval_code_quality.prompty",
            model={"configuration": self.model_config},
        )
        output = prompty(code=code)
        output = json.loads(output)
        output = Result(**output)
        return output

    def __aggregate__(self, line_results: list) -> dict:
        """Aggregate the results."""
        total = len(line_results)
        avg_correctness = sum(int(r["correctness"]) for r in line_results) / total
        avg_readability = sum(int(r["readability"]) for r in line_results) / total
        return {
            "average_correctness": avg_correctness,
            "average_readability": avg_readability,
            "total": total,
        }


if __name__ == "__main__":
    from promptflow.tracing import start_trace

    start_trace()
    model_config = AzureOpenAIModelConfiguration(
        connection="open_ai_connection",
        azure_deployment="gpt-4o",
    )
    evaluator = CodeEvaluator(model_config)
    result = evaluator('print("Hello, world!")')
    print(result)
    aggregate_result = evaluator.__aggregate__([result])
    print(aggregate_result)
