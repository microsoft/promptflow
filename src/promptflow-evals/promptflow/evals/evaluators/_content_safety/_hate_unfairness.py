from pathlib import Path

from promptflow.client import load_flow

from .flow.constants import EvaluationMetrics
from ._content_safety_sub_evaluator_base import ContentSafetySubEvaluatorBase

class HateUnfairnessEvaluator(ContentSafetySubEvaluatorBase):
    """
    Initialize a hate-unfairness evaluator for hate unfairness score.

    :param project_scope: The scope of the Azure AI project.
        It contains subscription id, resource group, and project name.
    :type project_scope: dict
    :param credential: The credential for connecting to Azure AI project.
    :type credential: TokenCredential

    **Usage**

    .. code-block:: python

        project_scope = {
            "subscription_id": "<subscription_id>",
            "resource_group_name": "<resource_group_name>",
            "project_name": "<project_name>",
        }
        eval_fn = HateUnfairnessEvaluator(project_scope)
        result = eval_fn(question="What is the capital of France?", answer="Paris.")

    **Output format**

    .. code-block:: python

        {
            "hate_unfairness": "High",
            "hate_unfairness_score": 6.5,
            "hate_unfairness_reason": "Some reason"
        }
    """

    def __init__(self, project_scope: dict, credential=None):
        super().__init__(
            metric=EvaluationMetrics.HATE_FAIRNESS,
            project_scope=project_scope,
            credential=credential,
        )

    def __call__(self, *, question: str, answer: str, **kwargs):
        """
        Evaluates hate unfairness content.

        :param question: The question to be evaluated.
        :type question: str
        :param answer: The answer to be evaluated.
        :type answer: str
        :return: The hate unfairness score.
        :rtype: dict
        """
        return super().__call__(question=question, answer=answer, **kwargs)
