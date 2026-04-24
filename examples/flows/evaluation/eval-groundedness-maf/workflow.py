import asyncio
import os
import re
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv
from typing_extensions import Never
from agent_framework import Agent, Executor, WorkflowBuilder, WorkflowContext, handler
from agent_framework.openai import OpenAIChatClient

load_dotenv()

# Load the .md prompt template (gap #13: .md files used as LLM prompts)
_PROMPT_TEMPLATE = (Path(__file__).parent / "gpt_groundedness.md").read_text(
    encoding="utf-8"
)


@dataclass
class EvalInput:
    question: str
    answer: str
    context: str


def _render_prompt(question: str, answer: str, context: str) -> str:
    """Render the .md prompt template by replacing {{variable}} placeholders."""
    prompt = _PROMPT_TEMPLATE
    prompt = prompt.replace("{{question}}", question)
    prompt = prompt.replace("{{answer}}", answer)
    prompt = prompt.replace("{{context}}", context)
    return prompt


def _parse_score(gpt_score: str) -> float:
    match = re.search(r"[-+]?\d*\.\d+|\d+", gpt_score)
    if match:
        return float(match.group())
    return 0.0


class GroundednessExecutor(Executor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        client = OpenAIChatClient(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            model=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4"),
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
        self._agent = Agent(client=client, name="GroundednessAgent", instructions="You are an evaluator.")

    @handler
    async def evaluate(self, input: EvalInput, ctx: WorkflowContext[Never, float]) -> None:
        prompt = _render_prompt(input.question, input.answer, input.context)
        response = await self._agent.run(prompt)
        score = _parse_score(response.text)
        await ctx.yield_output(score)


def create_workflow():
    _groundedness = GroundednessExecutor(id="groundedness")
    return WorkflowBuilder(name="EvalGroundednessRow", start_executor=_groundedness).build()
