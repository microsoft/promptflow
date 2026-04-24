import asyncio
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from jinja2 import Template
from openai import AsyncAzureOpenAI
from tenacity import (
    RetryError,
    retry,
    stop_after_attempt,
    wait_random_exponential,
)
from typing_extensions import Never
from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler

load_dotenv()

logger = logging.getLogger(__name__)

# Load Jinja2 prompt templates (gap #3: type:prompt as Jinja2 render)
_PROMPTS_DIR = Path(__file__).parent / "prompts"
_COHERENCE_TEMPLATE = Template(_PROMPTS_DIR.joinpath("coherence.jinja2").read_text(encoding="utf-8"))
_CONSISTENCY_TEMPLATE = Template(_PROMPTS_DIR.joinpath("consistency.jinja2").read_text(encoding="utf-8"))
_FLUENCY_TEMPLATE = Template(_PROMPTS_DIR.joinpath("fluency.jinja2").read_text(encoding="utf-8"))
_RELEVANCE_TEMPLATE = Template(_PROMPTS_DIR.joinpath("relevance.jinja2").read_text(encoding="utf-8"))

# Dimension configs: (template, max_score, needs_document)
_DIMENSIONS = {
    "coherence": (_COHERENCE_TEMPLATE, 5, True),
    "consistency": (_CONSISTENCY_TEMPLATE, 5, True),
    "fluency": (_FLUENCY_TEMPLATE, 3, False),
    "relevance": (_RELEVANCE_TEMPLATE, 5, True),
}


@dataclass
class EvalInput:
    document: str
    summary: str


def _parse_output(output: str, max_score: float) -> float:
    matched = re.findall(r"(?<!\S)\d+(?:\.\d+)?", output)
    if matched:
        if len(matched) == 1:
            score = float(matched[0])
            if score > max_score:
                raise ValueError(f"Parsed number: {score} was larger than max score: {max_score}")
        else:
            raise ValueError(f"More than one number detected in input: {output}")
    else:
        raise ValueError(f'No number detected in input: "{output}"')
    return score


def _aggregate_llm_scores(llm_responses: List[str], max_score: float) -> float:
    all_scores = []
    error_count = 0
    for generated in llm_responses:
        try:
            parsed = _parse_output(generated, max_score)
            all_scores.append(parsed)
        except ValueError as e:
            logger.warning(e)
            error_count += 1
    if error_count:
        logger.warning(f"{error_count} out of {len(llm_responses)} scores were discarded")
    if not all_scores:
        return 0.0
    return sum(all_scores) / len(all_scores)


class SummarizationGEvalExecutor(Executor):
    """Runs G-Eval (n=20 sampling) for all 4 summarization dimensions.

    Uses raw openai SDK because MAF Agent doesn't support n>1 (gap #9).
    Uses AzureOpenAI client directly (gap #6: AzureOpenAIConnection in Python).
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._client = AsyncAzureOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01"),
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
        self._deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4")

    @retry(wait=wait_random_exponential(multiplier=1, min=1, max=120), stop=stop_after_attempt(10), reraise=True)
    async def _call_geval(self, prompt: str) -> list:
        response = await self._client.chat.completions.create(
            model=self._deployment,
            messages=[{"role": "system", "content": prompt}],
            temperature=2,
            max_tokens=5,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
            n=20,
        )
        responses = []
        for choice in response.choices:
            try:
                responses.append(choice.message.content)
            except (KeyError, AttributeError):
                pass
        return responses

    async def _score_dimension(self, name: str, document: str, summary: str) -> float:
        template, max_score, needs_doc = _DIMENSIONS[name]
        if needs_doc:
            prompt = template.render(Document=document, Summary=summary)
        else:
            prompt = template.render(Summary=summary)
        responses = await self._call_geval(prompt)
        return _aggregate_llm_scores(responses, max_score)

    @handler
    async def evaluate(self, input: EvalInput, ctx: WorkflowContext[Never, dict]) -> None:
        # Run all 4 dimensions concurrently
        results = await asyncio.gather(
            self._score_dimension("coherence", input.document, input.summary),
            self._score_dimension("consistency", input.document, input.summary),
            self._score_dimension("fluency", input.document, input.summary),
            self._score_dimension("relevance", input.document, input.summary),
        )
        await ctx.yield_output({
            "coherence": results[0],
            "consistency": results[1],
            "fluency": results[2],
            "relevance": results[3],
        })


def create_workflow():
    _geval = SummarizationGEvalExecutor(id="geval_summarization")
    return WorkflowBuilder(name="EvalSummarizationRow", start_executor=_geval).build()
