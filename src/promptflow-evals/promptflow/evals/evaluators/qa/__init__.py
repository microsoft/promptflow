# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

__path__ = __import__("pkgutil").extend_path(__path__, __name__)  # type: ignore

from promptflow import load_flow
from promptflow.entities import AzureOpenAIConnection
from pathlib import Path


def init(model_config: AzureOpenAIConnection, deployment_name: str):
    """
    Initialize an evaluation function configured for a specific Azure OpenAI model.

    :param model_config: Configuration for the Azure OpenAI model.
    :type model_config: AzureOpenAIConnection
    :return: A function that evaluates and generates metrics for "question-answering" scenario.
    :rtype: function

    **Usage**

    .. code-block:: python

        eval_fn = qa.init(model_config, deployment_name="gpt-4")
        result = qa_eval(
        question="Tokyo is the capital of which country?",
        answer="Japan",
        context="Tokyo is the capital of Japan.",
        ground_truth="Japan",
    )
    """

    def eval_fn(*, answer: str, question: str = None, context: str = None, ground_truth: str = None, **kwargs):
        # TODO: How to parallelize metrics calculation
        from promptflow.evals.evaluators import groundedness, f1_score

        groundedness_eval = groundedness.init(model_config, deployment_name=deployment_name)
        f1_score_eval = f1_score.init()

        return {
            **groundedness_eval(answer=answer, context=context),
            **f1_score_eval(answer=answer, ground_truth=ground_truth)
        }

    return eval_fn


class QAEvaluator:
    """
        Initialize an evaluation function configured for a specific Azure OpenAI model.

        :param model_config: Configuration for the Azure OpenAI model.
        :type model_config: AzureOpenAIConnection
        :return: A function that evaluates and generates metrics for "question-answering" scenario.
        :rtype: function

        **Usage**

        .. code-block:: python

            eval_fn = QAEvaluator(model_config, deployment_name="gpt-4")
            result = qa_eval(
            question="Tokyo is the capital of which country?",
            answer="Japan",
            context="Tokyo is the capital of Japan.",
            ground_truth="Japan",
        )
        """

    def __init__(self, *, model_config: AzureOpenAIConnection, deployment_name: str):
        self.model_config = model_config
        self.deployment_name = deployment_name
        self._evaluators = self._init_evaluators()

    def _init_evaluators(self):
        from promptflow.evals.evaluators import GroundednessEvaluator, F1ScoreEvaluator
        return [
            GroundednessEvaluator(model_config=self.model_config, deployment_name=self.deployment_name),
            F1ScoreEvaluator()
        ]

    def __call__(self, *, answer: str, question: str = None, context: str = None, ground_truth: str = None, **kwargs):
        # TODO: How to parallelize metrics calculation

        return {
            k: v for d in
            [evaluator(answer=answer, context=context, ground_truth=ground_truth, question=question) for evaluator in
             self._evaluators]
            for k, v in d.items()
        }
