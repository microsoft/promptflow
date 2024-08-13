# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import asyncio

from promptflow._utils.async_utils import async_run_allowing_running_loop
from promptflow.core import AzureOpenAIModelConfiguration

from .._coherence import CoherenceEvaluator
from .._f1_score import F1ScoreEvaluator
from .._fluency import FluencyEvaluator
from .._groundedness import GroundednessEvaluator
from .._relevance import RelevanceEvaluator
from .._similarity import SimilarityEvaluator


class _AsyncQAEvaluator:
    def __init__(self, model_config: AzureOpenAIModelConfiguration, parallel: bool = True):
        self._parallel = parallel

        self._evaluators = [
            GroundednessEvaluator(model_config)._to_async(),
            RelevanceEvaluator(model_config)._to_async(),
            CoherenceEvaluator(model_config)._to_async(),
            FluencyEvaluator(model_config)._to_async(),
            SimilarityEvaluator(model_config)._to_async(),
            F1ScoreEvaluator()._to_async(),
        ]

    async def __call__(self, *, question: str, answer: str, context: str, ground_truth: str, **kwargs):
        results = {}

        if self._parallel:
            tasks = []
            for evaluator in self._evaluators:
                tasks.append(
                    asyncio.create_task(
                        evaluator(
                            question=question, answer=answer, context=context, ground_truth=ground_truth, **kwargs
                        )
                    )
                )
            completed_results = await asyncio.gather(*tasks)
            for result in completed_results:
                results.update(result)
        else:
            for evaluator in self._evaluators:
                result = await evaluator(
                    question=question, answer=answer, context=context, ground_truth=ground_truth, **kwargs
                )
                results.update(result)

        return results


class QAEvaluator:
    """
    Initialize a question-answer evaluator configured for a specific Azure OpenAI model.

    :param model_config: Configuration for the Azure OpenAI model.
    :type model_config: ~promptflow.core.AzureOpenAIModelConfiguration
    :return: A function that evaluates and generates metrics for "question-answering" scenario.
    :rtype: Callable

    **Usage**

    .. code-block:: python

        eval_fn = QAEvaluator(model_config)
        result = qa_eval(
            question="Tokyo is the capital of which country?",
            answer="Japan",
            context="Tokyo is the capital of Japan.",
            ground_truth="Japan"
        )

    **Output format**

    .. code-block:: python

        {
            "gpt_groundedness": 3.5,
            "gpt_relevance": 4.0,
            "gpt_coherence": 1.5,
            "gpt_fluency": 4.0,
            "gpt_similarity": 3.0,
            "f1_score": 0.42
        }
    """

    def __init__(self, model_config: AzureOpenAIModelConfiguration, parallel: bool = True):
        self._async_evaluator = _AsyncQAEvaluator(model_config, parallel)

    def __call__(self, *, question: str, answer: str, context: str, ground_truth: str, **kwargs):
        """
        Evaluates question-answering scenario.

        :keyword question: The question to be evaluated.
        :paramtype question: str
        :keyword answer: The answer to be evaluated.
        :paramtype answer: str
        :keyword context: The context to be evaluated.
        :paramtype context: str
        :keyword ground_truth: The ground truth to be evaluated.
        :paramtype ground_truth: str
        :keyword parallel: Whether to evaluate in parallel. Defaults to True.
        :paramtype parallel: bool
        :return: The scores for QA scenario.
        :rtype: dict
        """
        return async_run_allowing_running_loop(
            self._async_evaluator,
            question=question,
            answer=answer,
            context=context,
            ground_truth=ground_truth,
            **kwargs
        )

    def _to_async(self):
        return self._async_evaluator
