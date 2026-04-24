import asyncio
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from typing import List, Optional

from dotenv import load_dotenv
from jinja2 import Template
from openai import AsyncAzureOpenAI
from typing_extensions import Never
from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler

load_dotenv()

# Load Jinja2 prompt templates
_TEMPLATES_DIR = Path(__file__).parent
_ANSWER_RELEVANCE_TEMPLATE = Template(
    _TEMPLATES_DIR.joinpath("answer_relevance.jinja2").read_text(encoding="utf-8")
)
_CONVERSATION_QUALITY_TEMPLATE = Template(
    _TEMPLATES_DIR.joinpath("conversation_quality_prompt.jinja2").read_text(encoding="utf-8")
)
_CREATIVITY_TEMPLATE = Template(
    _TEMPLATES_DIR.joinpath("creativity.jinja2").read_text(encoding="utf-8")
)
_GROUNDING_PROMPT = _TEMPLATES_DIR.joinpath("grounding_prompt.jinja2").read_text(encoding="utf-8")

SUPPORTED_METRICS = ("answer_relevance", "conversation_quality", "creativity", "grounding")


@dataclass
class EvalInput:
    chat_history: list
    metrics: str = "creativity,conversation_quality,answer_relevance,grounding"


def _select_metrics(metrics_str: str) -> dict:
    user_selected = [m.strip() for m in metrics_str.split(",") if m.strip()]
    return {m: (m in user_selected) for m in SUPPORTED_METRICS}


def _validate_input(chat_history: list, selected_metrics: dict) -> dict:
    dict_metric_required_fields = {
        "answer_relevance": {"question", "answer"},
        "conversation_quality": {"question", "answer"},
        "creativity": {"question", "answer"},
        "grounding": {"answer", "context"},
    }
    actual_input_cols = set()
    for item in chat_history[:1]:
        actual_input_cols.update(item.get("inputs", {}).keys())
        actual_input_cols.update(item.get("outputs", {}).keys())

    data_validation = dict(selected_metrics)
    for metric in selected_metrics:
        if selected_metrics[metric]:
            if not dict_metric_required_fields[metric] <= actual_input_cols:
                data_validation[metric] = False
    return data_validation


def _convert_chat_history_to_conversation(chat_history: list) -> str:
    conversation = ""
    for i in chat_history:
        conversation += f"User: {i['inputs']['question']}\nBot: {i['outputs']['answer']}\n"
    return conversation


def _get_score(result: Optional[str]) -> Optional[float]:
    if result is None:
        return None
    try:
        result_dict = json.loads(result)
        score = result_dict.get("score", None)
        return score
    except json.JSONDecodeError:
        return None


class MultiTurnMetricsExecutor(Executor):
    """Evaluates multi-turn conversations on up to 4 metrics.

    Handles conditional metric activation (gap #4), multi-turn grounding iteration
    (gap #10), and dot-notation output access (gap #11) all within a single executor.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._client = AsyncAzureOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01"),
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
        self._deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4")

    async def _llm_call(self, prompt: str) -> str:
        response = await self._client.chat.completions.create(
            model=self._deployment,
            messages=[{"role": "system", "content": prompt}],
            temperature=0,
            top_p=1,
            presence_penalty=0,
            frequency_penalty=0,
        )
        return response.choices[0].message.content or ""

    async def _eval_answer_relevance(self, conversation: str) -> Optional[float]:
        prompt = _ANSWER_RELEVANCE_TEMPLATE.render(conversation=conversation)
        result = await self._llm_call(prompt)
        return _get_score(result)

    async def _eval_conversation_quality(self, conversation: str) -> Optional[float]:
        prompt = _CONVERSATION_QUALITY_TEMPLATE.render(conversation=conversation)
        result = await self._llm_call(prompt)
        return _get_score(result)

    async def _eval_creativity(self, conversation: str) -> Optional[float]:
        prompt = _CREATIVITY_TEMPLATE.render(conversation=conversation)
        result = await self._llm_call(prompt)
        return _get_score(result)

    async def _eval_grounding(self, chat_history: list) -> Optional[float]:
        """Iterates through chat_history turns, calls LLM per turn, averages scores (gap #10)."""
        scores = []
        for item in chat_history:
            context = item["outputs"].get("context", "")
            answer = item["outputs"].get("answer", "")
            prompt = _GROUNDING_PROMPT.replace("{context}", context).replace("{answer}", answer)
            result = await self._llm_call(prompt)
            try:
                scores.append(int(result.strip()))
            except (ValueError, TypeError):
                pass
        if scores:
            return mean(scores)
        return None

    @handler
    async def evaluate(self, input: EvalInput, ctx: WorkflowContext[Never, dict]) -> None:
        selected = _select_metrics(input.metrics)
        validated = _validate_input(input.chat_history, selected)
        conversation = _convert_chat_history_to_conversation(input.chat_history)

        tasks = {}
        if validated.get("answer_relevance"):
            tasks["answer_relevance"] = self._eval_answer_relevance(conversation)
        if validated.get("conversation_quality"):
            tasks["conversation_quality"] = self._eval_conversation_quality(conversation)
        if validated.get("creativity"):
            tasks["creativity"] = self._eval_creativity(conversation)
        if validated.get("grounding"):
            tasks["grounding"] = self._eval_grounding(input.chat_history)

        results_dict = {}
        if tasks:
            keys = list(tasks.keys())
            values = await asyncio.gather(*tasks.values())
            for k, v in zip(keys, values):
                results_dict[k] = v

        # Fill in None for metrics that were not computed
        for metric in SUPPORTED_METRICS:
            if metric not in results_dict:
                results_dict[metric] = None

        await ctx.yield_output(results_dict)


def create_workflow():
    _executor = MultiTurnMetricsExecutor(id="multi_turn_metrics")
    return WorkflowBuilder(name="EvalMultiTurnMetricsRow", start_executor=_executor).build()
