# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
try:
    from ._content_safety_sub_evaluator_base import ContentSafetySubEvaluatorBase
    from .common.constants import EvaluationMetrics
except ImportError:
    from _content_safety_sub_evaluator_base import ContentSafetySubEvaluatorBase
    from common.constants import EvaluationMetrics


class SelfHarmEvaluator(ContentSafetySubEvaluatorBase):
    """
    Initialize a self harm evaluator for self harm score.

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
        eval_fn = SelfHarmEvaluator(project_scope)
        result = eval_fn(question="What is the capital of France?", answer="Paris.")

    **Output format**

    .. code-block:: python

        {
            "self_harm": "High",
            "self_harm_score": 6.5,
            "self_harm_reason": "Some reason"
        }
    """

    def __init__(self, project_scope: dict, credential=None):
        super().__init__(
            metric=EvaluationMetrics.SELF_HARM,
            project_scope=project_scope,
            credential=credential,
        )
