# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

__path__ = __import__("pkgutil").extend_path(__path__, __name__)  # type: ignore

from promptflow.entities import AzureOpenAIConnection
from promptflow.evals.evaluators import GroundednessEvaluator, RelevanceEvaluator, CoherenceEvaluator, FluencyEvaluator, SimilarityEvaluator, F1ScoreEvaluator




class QAEvaluator:
    def __init__(self, model_config: AzureOpenAIConnection, deployment_name: str):
        """
        Initialize an evaluator configured for a specific Azure OpenAI model.

        :param model_config: Configuration for the Azure OpenAI model.
        :type model_config: AzureOpenAIConnection
        :param deployment_name: Deployment to be used which has Azure OpenAI model.
        :type deployment_name: AzureOpenAIConnection
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
        self._evaluators  = [
            GroundednessEvaluator(model_config, deployment_name=deployment_name),
            RelevanceEvaluator(model_config, deployment_name=deployment_name),
            CoherenceEvaluator(model_config, deployment_name=deployment_name),
            FluencyEvaluator(model_config, deployment_name=deployment_name),
            SimilarityEvaluator(model_config, deployment_name=deployment_name),
            F1ScoreEvaluator(),
        ]

    def __call__(self, *, question: str, answer: str, context: str, ground_truth: str, **kwargs):
        """Evaluate similarity.

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
            k: v for d in
            [evaluator(answer=answer, context=context, ground_truth=ground_truth, question=question) for evaluator in
                self._evaluators]
            for k, v in d.items()
        }