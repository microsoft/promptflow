import asyncio
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from dotenv import load_dotenv
from jinja2 import Template
from openai import AsyncAzureOpenAI
from typing_extensions import Never
from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler

load_dotenv()

SUPPORTED_METRICS = ("gpt_relevance", "gpt_groundedness", "gpt_retrieval_score")

# Load Jinja2 prompt templates
_TEMPLATES_DIR = Path(__file__).parent
_TEMPLATES = {}
for name in ["rag_groundedness_prompt", "rag_retrieval_prompt", "rag_generation_prompt"]:
    path = _TEMPLATES_DIR / f"{name}.jinja2"
    if path.exists():
        _TEMPLATES[name] = Template(path.read_text(encoding="utf-8"))


@dataclass
class EvalInput:
    question: str
    answer: str
    documents: str
    metrics: str = "gpt_groundedness,gpt_relevance,gpt_retrieval_score"


def _select_metrics(metrics_str: str) -> dict:
    user_selected = [m.strip() for m in metrics_str.split(",") if m.strip()]
    return {m: (m in user_selected) for m in SUPPORTED_METRICS}


def _validate_input(question: str, answer: str, documents: str, selected_metrics: dict) -> dict:
    dict_metric_required_fields = {
        "gpt_groundedness": {"question", "answer", "documents"},
        "gpt_relevance": {"question", "answer", "documents"},
        "gpt_retrieval_score": {"question", "documents"},
    }
    input_data = {"question": question, "answer": answer, "documents": documents}
    actual_input_cols = {col for col, val in input_data.items() if val and val.strip()}
    data_validation = dict(selected_metrics)
    for metric in selected_metrics:
        if selected_metrics[metric]:
            if not dict_metric_required_fields[metric] <= actual_input_cols:
                data_validation[metric] = False
    return data_validation


def _parse_groundedness_score(raw: str) -> dict:
    try:
        numbers_found = re.findall(r"Quality score:\s*(\d+)\/\d", raw)
        score = float(numbers_found[0]) if numbers_found else 0
    except Exception:
        score = float("nan")
    try:
        quality_reasoning, _ = raw.split("Quality score: ")
    except Exception:
        quality_reasoning = raw
    return {"quality_score": score, "quality_reasoning": quality_reasoning}


def _parse_generation_score(raw: str) -> dict:
    quality_score = float("nan")
    quality_reasoning = ""
    for sent in raw.split("\n"):
        sent = sent.strip()
        if re.match(r"\s*(<)?Quality score:", sent):
            numbers_found = re.findall(r"(\d+\.*\d*)\/", sent)
            if numbers_found:
                quality_score = int(float(numbers_found[0].replace("'", "")))
    for sent in raw.split("\n"):
        sent = sent.strip()
        if re.match(r"\s*(<)?Quality score reasoning:", sent):
            quality_reasoning = sent.strip()
            break
    return {"quality_score": quality_score, "quality_reasoning": quality_reasoning}


def _parse_retrieval_score(raw: str) -> dict:
    score_response = [
        sent.strip() for sent in raw.strip('"').split("# Result")[-1].strip().split(".")
        if sent.strip()
    ]
    parsed = re.findall(r"\d+", score_response[-1]) if score_response else []
    if parsed:
        score = float(parsed[-1].strip())
        if score < 1.0 or score > 5.0:
            score = float("nan")
    else:
        score = float("nan")
    try:
        reasoning_response, _ = raw.split("# Result")
    except Exception:
        reasoning_response = raw
    return {"quality_score": score, "quality_reasoning": reasoning_response}


class QnaRagMetricsExecutor(Executor):
    """Evaluates QnA RAG on 3 metrics: groundedness, relevance, retrieval."""

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
            temperature=0, top_p=1, max_tokens=1000,
            presence_penalty=0, frequency_penalty=0,
        )
        return response.choices[0].message.content or ""

    async def _eval_groundedness(self, question: str, answer: str, documents: str) -> Optional[dict]:
        template = _TEMPLATES.get("rag_groundedness_prompt")
        if not template:
            return None
        prompt = template.render(question=question, answer=answer, FullBody=documents)
        raw = await self._llm_call(prompt)
        return _parse_groundedness_score(raw)

    async def _eval_relevance(self, question: str, answer: str, documents: str) -> Optional[dict]:
        template = _TEMPLATES.get("rag_generation_prompt")
        if not template:
            return None
        prompt = template.render(question=question, answer=answer, FullBody=documents)
        raw = await self._llm_call(prompt)
        return _parse_generation_score(raw)

    async def _eval_retrieval(self, question: str, documents: str) -> Optional[dict]:
        template = _TEMPLATES.get("rag_retrieval_prompt")
        if not template:
            return None
        prompt = template.render(question=question, FullBody=documents)
        raw = await self._llm_call(prompt)
        return _parse_retrieval_score(raw)

    @handler
    async def evaluate(self, input: EvalInput, ctx: WorkflowContext[Never, dict]) -> None:
        selected = _select_metrics(input.metrics)
        validated = _validate_input(input.question, input.answer, input.documents, selected)

        tasks = {}
        if validated.get("gpt_groundedness"):
            tasks["gpt_groundedness"] = self._eval_groundedness(input.question, input.answer, input.documents)
        if validated.get("gpt_relevance"):
            tasks["gpt_relevance"] = self._eval_relevance(input.question, input.answer, input.documents)
        if validated.get("gpt_retrieval_score"):
            tasks["gpt_retrieval_score"] = self._eval_retrieval(input.question, input.documents)

        parsed_results = {}
        if tasks:
            keys = list(tasks.keys())
            values = await asyncio.gather(*tasks.values())
            for k, v in zip(keys, values):
                parsed_results[k] = v

        # Extract quality_score from each parsed result
        variant_result = {}
        for metric in SUPPORTED_METRICS:
            parsed = parsed_results.get(metric)
            if parsed:
                try:
                    variant_result[metric] = float(parsed["quality_score"])
                except (ValueError, TypeError, KeyError):
                    variant_result[metric] = np.nan
            else:
                variant_result[metric] = np.nan

        await ctx.yield_output(variant_result)


def create_workflow():
    _executor = QnaRagMetricsExecutor(id="qna_rag_metrics")
    return WorkflowBuilder(name="EvalQnaRagMetricsRow", start_executor=_executor).build()
