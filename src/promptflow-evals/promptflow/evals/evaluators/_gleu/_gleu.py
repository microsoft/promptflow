# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from nltk.translate.gleu_score import sentence_gleu

from promptflow._utils.async_utils import async_run_allowing_running_loop
from promptflow.evals._common.utils import nltk_tokenize


class _AsyncGleuScoreEvaluator:
    def __init__(self):
        pass

    async def __call__(self, *, ground_truth: str, answer: str, **kwargs):
        reference_tokens = nltk_tokenize(ground_truth)
        hypothesis_tokens = nltk_tokenize(answer)

        score = sentence_gleu([reference_tokens], hypothesis_tokens)

        return {
            "gleu_score": score,
        }


class GleuScoreEvaluator:
    """
    Evaluator that computes the BLEU Score between two strings.

    The GLEU (Google-BLEU) score evaluator measures the similarity between generated and reference texts by
    evaluating n-gram overlap, considering both precision and recall. This balanced evaluation, designed for
    sentence-level assessment, makes it ideal for detailed analysis of translation quality. GLEU is well-suited for
    use cases such as machine translation, text summarization, and text generation.

    **Usage**

    .. code-block:: python

        eval_fn = GleuScoreEvaluator()
        result = eval_fn(
            answer="Tokyo is the capital of Japan.",
            ground_truth="The capital of Japan is Tokyo.")

    **Output format**

    .. code-block:: python

        {
            "gleu_score": 0.41
        }
    """

    def __init__(self):
        self._async_evaluator = _AsyncGleuScoreEvaluator()

    def __call__(self, *, ground_truth: str, answer: str, **kwargs):
        """
        Evaluate the GLEU score between the answer and the ground truth.

        :keyword answer: The answer to be evaluated.
        :paramtype answer: str
        :keyword ground_truth: The ground truth to be compared against.
        :paramtype ground_truth: str
        :return: The GLEU score.
        :rtype: dict
        """
        return async_run_allowing_running_loop(
            self._async_evaluator, ground_truth=ground_truth, answer=answer, **kwargs
        )

    def _to_async(self):
        return self._async_evaluator
