# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from enum import Enum

from rouge_score import rouge_scorer

from promptflow._utils.async_utils import async_run_allowing_running_loop


class RougeType(str, Enum):
    """
    Enumeration of ROUGE (Recall-Oriented Understudy for Gisting Evaluation) types.
    """

    ROUGE_1 = "rouge1"
    """Overlap of unigrams (single words) between generated and reference text."""

    ROUGE_2 = "rouge2"
    """Overlap of bigrams (two consecutive words) between generated and reference text."""

    ROUGE_3 = "rouge3"
    """Overlap of trigrams (three consecutive words) between generated and reference text."""

    ROUGE_4 = "rouge4"
    """Overlap of four-grams (four consecutive words) between generated and reference text."""

    ROUGE_5 = "rouge5"
    """Overlap of five-grams (five consecutive words) between generated and reference text."""

    ROUGE_L = "rougeL"
    """Overlap of L-grams (L consecutive words) between generated and reference text."""


class _AsyncRougeScoreEvaluator:
    def __init__(self, rouge_type: RougeType):
        self._rouge_type = rouge_type

    async def __call__(self, *, ground_truth: str, answer: str, **kwargs):
        scorer = rouge_scorer.RougeScorer(rouge_types=[self._rouge_type])
        metrics = scorer.score(ground_truth, answer)[self._rouge_type]
        return {
            "rouge_precision": metrics.precision,
            "rouge_recall": metrics.recall,
            "rouge_f1_score": metrics.fmeasure,
        }


class RougeScoreEvaluator:
    """
    Evaluator for computes the ROUGE scores between two strings.

    ROUGE (Recall-Oriented Understudy for Gisting Evaluation) is a set of metrics used to evaluate automatic
    summarization and machine translation. It measures the overlap between generated text and reference summaries.
    ROUGE focuses on recall-oriented measures to assess how well the generated text covers the reference text. Text
    summarization and document comparison are among optimal use cases for ROUGE, particularly in scenarios where text
    coherence and relevance are critical.

    **Usage**

    .. code-block:: python

        eval_fn = RougeScoreEvaluator(rouge_type=RougeType.ROUGE_1)
        result = eval_fn(
            answer="Tokyo is the capital of Japan.",
            ground_truth="The capital of Japan is Tokyo.")

    **Output format**

    .. code-block:: python

        {
            "rouge_precision": 1.0,
            "rouge_recall": 1.0,
            "rouge_f1_score": 1.0
        }
    """

    def __init__(self, rouge_type: RougeType):
        self._rouge_type = rouge_type
        self._async_evaluator = _AsyncRougeScoreEvaluator(rouge_type)

    def __call__(self, *, ground_truth: str, answer: str, **kwargs):
        """
        Evaluate the ROUGE score between the answer and the ground truth.

        :keyword answer: The answer to be evaluated.
        :paramtype answer: str
        :keyword ground_truth: The ground truth to be compared against.
        :paramtype ground_truth: str
        :return: The ROUGE score.
        :rtype: dict
        """
        return async_run_allowing_running_loop(
            self._async_evaluator, ground_truth=ground_truth, answer=answer, **kwargs
        )

    def _to_async(self):
        return self._async_evaluator
