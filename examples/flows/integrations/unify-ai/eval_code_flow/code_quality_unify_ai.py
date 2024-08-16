import json
from pathlib import Path
from typing import TypedDict

from jinja2 import Template

from promptflow.core import OpenAIModelConfiguration
from promptflow.core._flow import Prompty
from promptflow.tracing import trace

BASE_DIR = Path(__file__).absolute().parent

# Derived from https://github.com/microsoft/promptflow/blob/main/examples/flex-flows/eval-code-quality/


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
    """ Uses Unify AI's LLM to evaluate a code block.
    Note:
    OpenAI client is being repurposed to call Unify AI API, Since Unify AI API is competable with OpenAI API.
    This enables reusing Promptflow's OpenAI integration/support with Unify AI.

    """
    def __init__(self, model_config: OpenAIModelConfiguration):
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
