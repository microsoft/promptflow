# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from nltk.translate.bleu_score import SmoothingFunction, sentence_bleu

from promptflow._utils.async_utils import async_run_allowing_running_loop
from promptflow.evals._common.utils import nltk_tokenize


class _AsyncBleuScoreEvaluator:
    def __init__(self):
        pass

    async def __call__(self, *, answer: str, ground_truth: str, **kwargs):
        reference_tokens = nltk_tokenize(ground_truth)
        hypothesis_tokens = nltk_tokenize(answer)

        smoothing_function = SmoothingFunction().method4
        score = sentence_bleu([reference_tokens], hypothesis_tokens, smoothing_function=smoothing_function)

        return {
            "bleu_score": score,
        }


class BleuScoreEvaluator:
    """
    Evaluator that computes the BLEU Score between two strings.

    BLEU (Bilingual Evaluation Understudy) score is commonly used in natural language processing (NLP) and machine
    translation. It is widely used in text summarization and text generation use cases. It evaluates how closely the
    generated text matches the reference text. The BLEU score ranges from 0 to 1, with higher scores indicating
    better quality.

    **Usage**

    .. code-block:: python

        eval_fn = BleuScoreEvaluator()
        result = eval_fn(
            answer="Tokyo is the capital of Japan.",
            ground_truth="The capital of Japan is Tokyo.")

    **Output format**

    .. code-block:: python

        {
            "bleu_score": 0.22
        }
    """

    def __init__(self):
        self._async_evaluator = _AsyncBleuScoreEvaluator()

    def __call__(self, *, answer: str, ground_truth: str, **kwargs):
        """
        Evaluate the BLEU score between the answer and the ground truth.

        :keyword answer: The answer to be evaluated.
        :paramtype answer: str
        :keyword ground_truth: The ground truth to be compared against.
        :paramtype ground_truth: str
        :return: The BLEU score.
        :rtype: dict
        """
        return async_run_allowing_running_loop(
            self._async_evaluator, answer=answer, ground_truth=ground_truth, **kwargs
        )

    def _to_async(self):
        return self._async_evaluator
