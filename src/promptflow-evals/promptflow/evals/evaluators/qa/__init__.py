# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

__path__ = __import__("pkgutil").extend_path(__path__, __name__)  # type: ignore

from typing import Optional

from promptflow.evals.evaluators import (
    CoherenceEvaluator,
    F1ScoreEvaluator,
    FluencyEvaluator,
    GroundednessEvaluator,
    RelevanceEvaluator,
    SimilarityEvaluator,
)


class QAEvaluator:
    def __init__(self, model_config,
                 log_level: Optional[int] = None):
        """
        Initialize an evaluator configured for a specific Azure OpenAI model.

        :param model_config: Configuration for the Azure OpenAI model.
        :type model_config: AzureOpenAIModelConfiguration
        :return: A function that evaluates and generates metrics for "question-answering" scenario.
        :rtype: function
        :param log_level: The logging level.
        :type log_level: Optional[int]

        **Usage**

        .. code-block:: python

            eval_fn = QAEvaluator(model_config)
            result = qa_eval(
                question="Tokyo is the capital of which country?",
                answer="Japan",
                context="Tokyo is the capital of Japan.",
                ground_truth="Japan",
        )
        """
        self._evaluators = [
            GroundednessEvaluator(model_config, log_level=log_level),
            RelevanceEvaluator(model_config, log_level=log_level),
            CoherenceEvaluator(model_config, log_level=log_level),
            FluencyEvaluator(model_config, log_level=log_level),
            SimilarityEvaluator(model_config, log_level=log_level),
            F1ScoreEvaluator(log_level=log_level),
        ]

    def __call__(self, *, question: str, answer: str, context: str, ground_truth: str, **kwargs):
        """Evaluates question-answering scenario.

        :param question: The question to be evaluated.
        :type question: str
        :param answer: The answer to be evaluated.
        :type answer: str
        :param context: The context to be evaluated.
        :type context: str
        :param ground_truth: The ground truth to be evaluated.
        :type ground_truth: str
        :return: The scores for QA scenario.
        :rtype: dict
        """
        # TODO: How to parallelize metrics calculation

        return {
            k: v
            for d in [
                evaluator(answer=answer, context=context, ground_truth=ground_truth, question=question)
                for evaluator in self._evaluators
            ]
            for k, v in d.items()
        }
