# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from nltk.translate.meteor_score import single_meteor_score

from promptflow._utils.async_utils import async_run_allowing_running_loop
from promptflow.evals._common.utils import nltk_tokenize


class _AsyncMeteorScoreEvaluator:
    def __init__(self, alpha: float = 0.9, beta: float = 3.0, gamma: float = 0.5):
        self._alpha = alpha
        self._beta = beta
        self._gamma = gamma

    async def __call__(self, *, ground_truth: str, answer: str, **kwargs):
        reference_tokens = nltk_tokenize(ground_truth)
        hypothesis_tokens = nltk_tokenize(answer)

        score = single_meteor_score(
            reference_tokens,
            hypothesis_tokens,
            alpha=self._alpha,
            beta=self._beta,
            gamma=self._gamma,
        )

        return {
            "meteor_score": score,
        }


class MeteorScoreEvaluator:
    """
    Evaluator that computes the METEOR Score between two strings.

    The METEOR (Metric for Evaluation of Translation with Explicit Ordering) score grader evaluates generated text by
    comparing it to reference texts, focusing on precision, recall, and content alignment. It addresses limitations of
    other metrics like BLEU by considering synonyms, stemming, and paraphrasing. METEOR score considers synonyms and
    word stems to more accurately capture meaning and language variations. In addition to machine translation and
    text summarization, paraphrase detection is an optimal use case for the METEOR score.

    :param alpha: The METEOR score alpha parameter. Default is 0.9.
    :type alpha: float
    :param beta: The METEOR score beta parameter. Default is 3.0.
    :type beta: float
    :param gamma: The METEOR score gamma parameter. Default is 0.5.
    :type gamma: float

    **Usage**

    .. code-block:: python

        eval_fn = MeteorScoreEvaluator(
            alpha=0.9,
            beta=3.0,
            gamma=0.5
        )
        result = eval_fn(
            answer="Tokyo is the capital of Japan.",
            ground_truth="The capital of Japan is Tokyo.")

    **Output format**

    .. code-block:: python

        {
            "meteor_score": 0.62
        }
    """

    def __init__(self, alpha: float = 0.9, beta: float = 3.0, gamma: float = 0.5):
        self._async_evaluator = _AsyncMeteorScoreEvaluator(alpha=alpha, beta=beta, gamma=gamma)

    def __call__(self, *, ground_truth: str, answer: str, **kwargs):
        """
        Evaluate the METEOR score between the answer and the ground truth.

        :keyword answer: The answer to be evaluated.
        :paramtype answer: str
        :keyword ground_truth: The ground truth to be compared against.
        :paramtype ground_truth: str
        :return: The METEOR score.
        :rtype: dict
        """
        return async_run_allowing_running_loop(
            self._async_evaluator, ground_truth=ground_truth, answer=answer, **kwargs
        )

    def _to_async(self):
        return self._async_evaluator
