import asyncio
import json
import math
import os
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
    "grounding", "answer_relevance", "answer_quality", "context_precision",
    "answer_similarity", "creativity", "context_recall", "answer_correctness",
)

# Load Jinja2 prompt templates
_TEMPLATES_DIR = Path(__file__).parent
_TEMPLATES = {}
for name in ["grounding", "answer_quality", "answer_similarity", "creativity",
             "context_recall", "context_precision", "answer_relevance", "answer_correctness"]:
    path = _TEMPLATES_DIR / f"{name}.jinja2"
    if path.exists():
        _TEMPLATES[name] = Template(path.read_text(encoding="utf-8"))


@dataclass
class EvalInput:
    question: str
    answer: str
    context: str
    ground_truth: str
    metrics: str = "grounding,answer_relevance,answer_quality,context_precision,answer_similarity,creativity,context_recall,answer_correctness"


def _select_metrics(metrics_str: str) -> dict:
    user_selected = [m.strip() for m in metrics_str.split(",") if m.strip()]
    return {m: (m in user_selected) for m in SUPPORTED_METRICS}


def _validate_input(question: str, answer: str, context: str, ground_truth: str,
                     selected_metrics: dict) -> dict:
    dict_metric_required_fields = {
        "answer_relevance": {"question", "answer"},
        "answer_quality": {"question", "answer"},
        "creativity": {"question", "answer"},
        "grounding": {"answer", "context"},
        "context_recall": {"question", "context", "ground_truth"},
        "context_precision": {"question", "context", "ground_truth"},
        "answer_similarity": {"question", "answer", "ground_truth"},
        "answer_correctness": {"question", "answer", "ground_truth"},
    }
    input_data = {"question": question, "answer": answer, "context": context, "ground_truth": ground_truth}
    actual_input_cols = {col for col, val in input_data.items() if val and val.strip()}

    data_validation = dict(selected_metrics)
    for metric in selected_metrics:
        if selected_metrics[metric]:
            if not dict_metric_required_fields[metric] <= actual_input_cols:
                data_validation[metric] = False
    if data_validation.get("answer_correctness"):
        data_validation["answer_similarity"] = True
    return data_validation


def _get_score(result: Optional[str]) -> Optional[float]:
    if result is None:
        return None
    try:
        result_dict = json.loads(result)
        return result_dict.get("score", None)
    except json.JSONDecodeError:
        return None


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    a_arr = np.array(a)
    b_arr = np.array(b)
    dot = np.dot(a_arr, b_arr)
    return dot / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr))


def _calculate_context_recall(llm_result: str) -> float:
    try:
        response = json.loads(llm_result)
        if response:
            result = response.get("result", "")
            if result:
                response_vals = [
                    int(item.get("attributed", "").lower() == "yes" or
                        item.get("attribited", "").lower() == "yes")
                    if item.get("attributed") or item.get("attribited")
                    else np.nan
                    for item in result
                ]
                denom = len(response_vals)
                numerator = sum(response_vals)
                score = 5 * numerator / denom
                return max(score, 1)
        return 1
    except Exception:
        return np.nan


def _calculate_answer_correctness(statement_result: str, similarity_score: float) -> float:
    try:
        weights = [0.75, 0.25]
        key_map = {
            "TP": "statements that are present in both the answer and the ground truth",
            "FP": "statements present in the answer but not found in the ground truth",
            "FN": "relevant statements found in the ground truth but omitted in the answer",
        }
        score = 0
        result = json.loads(statement_result)
        if result:
            prediction = [result.get(key_map[k], np.nan) for k in key_map.keys()]
            tp, fp, fn = [len(item) if isinstance(item, list) else np.nan for item in prediction]
            score = 5 * tp / (tp + 0.5 * (fp + fn))
        final_score = weights[0] * score + weights[1] * int(similarity_score)
        return max(final_score, 1)
    except Exception:
        return np.nan


class SingleTurnMetricsExecutor(Executor):
    """Evaluates single-turn QA on up to 8 metrics.

    Handles conditional activation (gap #4), embedding calls (gap #8),
    and dot-notation output access (gap #11) all within a single executor.
    """

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
            temperature=0, top_p=1, presence_penalty=0, frequency_penalty=0,
        )
        return response.choices[0].message.content or ""

    async def _embed(self, text: str) -> List[float]:
        response = await self._client.embeddings.create(
            model=self._embedding_deployment, input=text,
        )
        return response.data[0].embedding

    async def _eval_simple_llm(self, metric_name: str, **template_vars) -> Optional[str]:
        template = _TEMPLATES.get(metric_name)
        if not template:
            return None
        prompt = template.render(**template_vars)
        return await self._llm_call(prompt)

    async def _eval_grounding(self, answer: str, context: str) -> Optional[float]:
        raw = await self._eval_simple_llm("grounding", answer=answer, context=context)
        return _get_score(raw) if raw else None

    async def _eval_answer_quality(self, question: str, answer: str) -> Optional[float]:
        raw = await self._eval_simple_llm("answer_quality", question=question, answer=answer)
        return _get_score(raw) if raw else None

    async def _eval_creativity(self, question: str, answer: str) -> Optional[float]:
        raw = await self._eval_simple_llm("creativity", question=question, answer=answer)
        return _get_score(raw) if raw else None

    async def _eval_context_precision(self, question: str, context: str, ground_truth: str) -> Optional[float]:
        raw = await self._eval_simple_llm("context_precision", question=question, context=context, ground_truth=ground_truth)
        return _get_score(raw) if raw else None

    async def _eval_answer_similarity(self, question: str, answer: str, ground_truth: str) -> Optional[float]:
        raw = await self._eval_simple_llm("answer_similarity", question=question, answer=answer, ground_truth=ground_truth)
        return _get_score(raw) if raw else None

    async def _eval_context_recall(self, question: str, context: str, ground_truth: str) -> Optional[float]:
        raw = await self._eval_simple_llm("context_recall", question=question, context=context, ground_truth=ground_truth)
        if raw is None:
            return None
        return _calculate_context_recall(raw)

    async def _eval_answer_relevance(self, question: str, answer: str, context: str) -> Optional[float]:
        raw = await self._eval_simple_llm("answer_relevance", answer=answer, context=context)
        if raw is None:
            return None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"question": "", "noncommittal": True}
        generated_q = parsed.get("question", "")
        noncommittal = parsed.get("noncommittal", True)
        q_embed, gq_embed = await asyncio.gather(
            self._embed(question), self._embed(generated_q)
        )
        cosine_sim = _cosine_similarity(q_embed, gq_embed)
        score = 5 * cosine_sim * int(not noncommittal)
        return max(score, 1)

    async def _eval_answer_correctness(self, question: str, answer: str,
                                        ground_truth: str, similarity_score: float) -> Optional[float]:
        raw = await self._eval_simple_llm("answer_correctness", question=question, answer=answer, ground_truth=ground_truth)
        if raw is None:
            return None
        return _calculate_answer_correctness(raw, similarity_score)

    @handler
    async def evaluate(self, input: EvalInput, ctx: WorkflowContext[Never, dict]) -> None:
        selected = _select_metrics(input.metrics)
        validated = _validate_input(input.question, input.answer, input.context, input.ground_truth, selected)

        results = {m: None for m in SUPPORTED_METRICS}

        # Phase 1: Run independent metrics concurrently
        tasks = {}
        if validated.get("grounding"):
            tasks["grounding"] = self._eval_grounding(input.answer, input.context)
        if validated.get("answer_quality"):
            tasks["answer_quality"] = self._eval_answer_quality(input.question, input.answer)
        if validated.get("creativity"):
            tasks["creativity"] = self._eval_creativity(input.question, input.answer)
        if validated.get("context_precision"):
            tasks["context_precision"] = self._eval_context_precision(input.question, input.context, input.ground_truth)
        if validated.get("context_recall"):
            tasks["context_recall"] = self._eval_context_recall(input.question, input.context, input.ground_truth)
        if validated.get("answer_relevance"):
            tasks["answer_relevance"] = self._eval_answer_relevance(input.question, input.answer, input.context)
        if validated.get("answer_similarity"):
            tasks["answer_similarity"] = self._eval_answer_similarity(input.question, input.answer, input.ground_truth)

        if tasks:
            keys = list(tasks.keys())
            values = await asyncio.gather(*tasks.values())
            for k, v in zip(keys, values):
                results[k] = v

        # Phase 2: answer_correctness depends on answer_similarity
        if validated.get("answer_correctness"):
            sim_score = results.get("answer_similarity") or 0
            results["answer_correctness"] = await self._eval_answer_correctness(
                input.question, input.answer, input.ground_truth, sim_score
            )

        await ctx.yield_output(results)


def create_workflow():
    _executor = SingleTurnMetricsExecutor(id="single_turn_metrics")
    return WorkflowBuilder(name="EvalSingleTurnMetricsRow", start_executor=_executor).build()
