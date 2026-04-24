import asyncio
import os
import re
import string
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np
from dotenv import load_dotenv
from jinja2 import Template
from openai import AsyncAzureOpenAI
from typing_extensions import Never
from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler

load_dotenv()

SUPPORTED_METRICS = (
    "gpt_groundedness", "f1_score", "ada_similarity",
    "gpt_fluency", "gpt_coherence", "gpt_similarity", "gpt_relevance",
)

# Load Jinja2 prompt templates
_TEMPLATES_DIR = Path(__file__).parent
_TEMPLATES = {}
for name in ["gpt_coherence_prompt", "gpt_similarity_prompt", "gpt_relevance_prompt",
             "gpt_fluency_prompt", "gpt_groundedness_prompt"]:
    path = _TEMPLATES_DIR / f"{name}.jinja2"
    if path.exists():
        _TEMPLATES[name] = Template(path.read_text(encoding="utf-8"))


@dataclass
class EvalInput:
    question: str
    answer: str
    context: str
    ground_truth: str
    metrics: str = "gpt_groundedness,f1_score,ada_similarity,gpt_fluency,gpt_coherence,gpt_similarity,gpt_relevance"


def _select_metrics(metrics_str: str) -> dict:
    user_selected = [m.strip() for m in metrics_str.split(",") if m.strip()]
    return {m: (m in user_selected) for m in SUPPORTED_METRICS}


def _validate_input(question: str, answer: str, context: str, ground_truth: str,
                     selected_metrics: dict) -> dict:
    dict_metric_required_fields = {
        "gpt_groundedness": {"answer", "context"},
        "gpt_relevance": {"question", "answer", "context"},
        "gpt_coherence": {"question", "answer"},
        "gpt_similarity": {"question", "answer", "ground_truth"},
        "gpt_fluency": {"question", "answer"},
        "f1_score": {"answer", "ground_truth"},
        "ada_similarity": {"answer", "ground_truth"},
    }
    input_data = {"question": question, "answer": answer, "context": context, "ground_truth": ground_truth}
    actual_input_cols = {col for col, val in input_data.items() if val and val.strip()}
    data_validation = dict(selected_metrics)
    for metric in selected_metrics:
        if selected_metrics[metric]:
            if not dict_metric_required_fields[metric] <= actual_input_cols:
                data_validation[metric] = False
    return data_validation


def _compute_f1_score(ground_truth: str, answer: str) -> float:
    def normalize_text(text: str) -> str:
        text = text.lower()
        text = "".join(ch for ch in text if ch not in set(string.punctuation))
        text = re.sub(r"\b(a|an|the)\b", " ", text)
        text = " ".join(text.split())
        return text

    prediction_tokens = normalize_text(answer).split()
    reference_tokens = normalize_text(ground_truth).split()
    common_tokens = Counter(prediction_tokens) & Counter(reference_tokens)
    num_common = sum(common_tokens.values())
    if num_common == 0:
        return 0.0
    precision = num_common / len(prediction_tokens)
    recall = num_common / len(reference_tokens)
    return (2.0 * precision * recall) / (precision + recall)


def _parse_gpt_score(raw: Optional[str]) -> float:
    if raw is None:
        return np.nan
    match = re.search(r"\d", raw)
    if match:
        return float(match.group())
    return np.nan


class QnaNonRagExecutor(Executor):
    """Evaluates QnA (non-RAG) on up to 7 metrics."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._client = AsyncAzureOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01"),
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
        self._deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
        self._embedding_deployment = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")

    async def _llm_call(self, prompt: str) -> str:
        response = await self._client.chat.completions.create(
            model=self._deployment,
            messages=[{"role": "system", "content": prompt}],
            temperature=0, top_p=1, max_tokens=1,
            presence_penalty=0, frequency_penalty=0,
        )
        return response.choices[0].message.content or ""

    async def _embed(self, text: str) -> List[float]:
        response = await self._client.embeddings.create(
            model=self._embedding_deployment, input=text,
        )
        return response.data[0].embedding

    async def _eval_gpt_metric(self, template_name: str, **vars) -> float:
        template = _TEMPLATES.get(template_name)
        if not template:
            return np.nan
        prompt = template.render(**vars)
        raw = await self._llm_call(prompt)
        return _parse_gpt_score(raw)

    async def _eval_ada_similarity(self, answer: str, ground_truth: str) -> float:
        emb_a, emb_b = await asyncio.gather(self._embed(ground_truth), self._embed(answer))
        a = np.array(emb_a)
        b = np.array(emb_b)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    @handler
    async def evaluate(self, input: EvalInput, ctx: WorkflowContext[Never, dict]) -> None:
        selected = _select_metrics(input.metrics)
        validated = _validate_input(input.question, input.answer, input.context, input.ground_truth, selected)

        tasks = {}
        if validated.get("gpt_coherence"):
            tasks["gpt_coherence"] = self._eval_gpt_metric("gpt_coherence_prompt", question=input.question, answer=input.answer)
        if validated.get("gpt_similarity"):
            tasks["gpt_similarity"] = self._eval_gpt_metric("gpt_similarity_prompt", question=input.question, answer=input.answer, ground_truth=input.ground_truth)
        if validated.get("gpt_relevance"):
            tasks["gpt_relevance"] = self._eval_gpt_metric("gpt_relevance_prompt", question=input.question, answer=input.answer, context=input.context)
        if validated.get("gpt_fluency"):
            tasks["gpt_fluency"] = self._eval_gpt_metric("gpt_fluency_prompt", question=input.question, answer=input.answer)
        if validated.get("gpt_groundedness"):
            tasks["gpt_groundedness"] = self._eval_gpt_metric("gpt_groundedness_prompt", answer=input.answer, context=input.context)
        if validated.get("ada_similarity"):
            tasks["ada_similarity"] = self._eval_ada_similarity(input.answer, input.ground_truth)

        results = {m: np.nan for m in SUPPORTED_METRICS}
        if tasks:
            keys = list(tasks.keys())
            values = await asyncio.gather(*tasks.values())
            for k, v in zip(keys, values):
                results[k] = v

        # f1_score is purely computational, no LLM needed
        if validated.get("f1_score"):
            results["f1_score"] = _compute_f1_score(input.ground_truth, input.answer)

        # Add pass_rate for gpt metrics
        variant_result = {}
        for name in SUPPORTED_METRICS:
            variant_result[name] = results[name]
            if "gpt" in name:
                try:
                    variant_result[name + "_pass_rate"] = 1 if float(results[name]) > 3 else 0
                except (ValueError, TypeError):
                    variant_result[name + "_pass_rate"] = 0

        await ctx.yield_output(variant_result)


def create_workflow():
    _executor = QnaNonRagExecutor(id="qna_non_rag")
    return WorkflowBuilder(name="EvalQnaNonRagRow", start_executor=_executor).build()
