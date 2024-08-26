# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from abc import ABC

from promptflow.evals._common.constants import EvaluationMetrics
from promptflow.evals._common.rai_service import evaluate_with_rai_service


class ContentSafetyEvaluatorBase(ABC):
    """
    Initialize a evaluator for a specified Evaluation Metric. Base class that is not
    meant to be instantiated by users.


    :param metric: The metric to be evaluated.
    :type metric: ~promptflow.evals.evaluators._content_safety.flow.constants.EvaluationMetrics
    :param project_scope: The scope of the Azure AI project.
        It contains subscription id, resource group, and project name.
    :type project_scope: Dict
    :param credential: The credential for connecting to Azure AI project.
    :type credential: ~azure.core.credentials.TokenCredential
    """

    def __init__(self, metric: EvaluationMetrics, project_scope: dict, credential=None):
        self._metric = metric
        self._project_scope = project_scope
        self._credential = credential

    async def __call__(self, *, question: str, answer: str, **kwargs):
        """
        Evaluates content according to this evaluator's metric.

        :keyword question: The question to be evaluated.
        :paramtype question: str
        :keyword answer: The answer to be evaluated.
        :paramtype answer: str
        :return: The evaluation score computation based on the Content Safety metric (self.metric).
        :rtype: Any
        """
        # Validate inputs
        # Raises value error if failed, so execution alone signifies success.
        if not (question and question.strip() and question != "None") or not (
            answer and answer.strip() and answer != "None"
        ):
            raise ValueError("Both 'question' and 'answer' must be non-empty strings.")

        # Run score computation based on supplied metric.
        result = await evaluate_with_rai_service(
            metric_name=self._metric,
            question=question,
            answer=answer,
            project_scope=self._project_scope,
            credential=self._credential,
        )
        return result
