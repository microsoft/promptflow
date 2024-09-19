# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging
from typing import Optional

from promptflow._utils.async_utils import async_run_allowing_running_loop
from promptflow.evals._common.constants import EvaluationMetrics
from promptflow.evals._common.rai_service import evaluate_with_rai_service

logger = logging.getLogger(__name__)


class IndirectAttackEvaluator:
    """
    Initializes an XPIA (cross domain prompt injected attack) jailbreak evaluator to detect whether cross domain
    injected attacks are present in your AI system's response.

    :param project_scope: The scope of the Azure AI project.
        It contains subscription id, resource group, and project name.
    :type project_scope: dict
    :param eval_last_turn: Set to True to evaluate only the most recent exchange in the dialogue,
        focusing on the latest user inquiry and the assistant's corresponding response. Defaults to False
    :type eval_last_turn: bool
    :param credential: The credential for connecting to Azure AI project.
    :type credential: ~azure.core.credentials.TokenCredential
    :return: A function that evaluates and generates metrics for XPIA chat scenario. Metrics include the overall
        evaluation label and reason for the Q/A Pair, as well as sub-labels
        for manipulated content, intrusion, and information.
    :rtype: Callable

    **Usage**

    .. code-block:: python

        eval_fn = IndirectAttackEvaluator(model_config)
        result = eval_fn(question="What is the capital of France?", answer="Paris.")

    **Output format for question-answer pair**

    .. code-block:: python

        {
            'xpia_label': False,
            'xpia_reason': 'The conversation does not contain any manipulated content, intrusion or
                          information gathering.'
            'xpia_information_gathering': False,
            'xpia_intrusion': False
            'xpia_manipulated_content': False
        }

    """

    def __init__(self, project_scope: dict, eval_last_turn: bool = False, credential=None):
        self._evaluator = _IndirectAttackEvaluator(project_scope, credential)
        self._eval_last_turn = eval_last_turn

    def __call__(
        self,
        *,
        question: Optional[str],
        answer: Optional[str],
        **kwargs,
    ):
        """
        Evaluates content according to the presence of attacks injected into the conversation context to
        interrupt normal expected functionality by eliciting manipulated content, intrusion and attempting
        to gather information outside the scope of your AI system.

        :keyword question: The question to be evaluated. Mutually exclusive with 'conversation'.
        :paramtype question: Optional[str]
        :keyword answer: The answer to be evaluated. Mutually exclusive with 'conversation'.
        :paramtype answer: Optional[str]
        :return: The evaluation scores and reasoning.
        :rtype: dict
        """

        return self._evaluator(question=question, answer=answer, **kwargs)


class _AsyncIndirectAttackEvaluator:
    def __init__(self, project_scope: dict, credential=None):
        self._project_scope = project_scope
        self._credential = credential

    async def __call__(self, *, question: str, answer: str, **kwargs):
        """
        Evaluates content according to this evaluator's metric.
        :keyword question: The question to be evaluated.
        :paramtype question: str
        :keyword answer: The answer to be evaluated.
        :paramtype answer: str
        :return: The evaluation score computation based on the metric (self.metric).
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
            metric_name=EvaluationMetrics.XPIA,
            question=question,
            answer=answer,
            project_scope=self._project_scope,
            credential=self._credential,
        )
        return result


class _IndirectAttackEvaluator:
    def __init__(self, project_scope: dict, credential=None):
        self._async_evaluator = _AsyncIndirectAttackEvaluator(project_scope, credential)

    def __call__(self, *, question: str, answer: str, **kwargs):
        """
        Evaluates XPIA content.
        :keyword question: The question to be evaluated.
        :paramtype question: str
        :keyword answer: The answer to be evaluated.
        :paramtype answer: str
        :keyword context: The context to be evaluated.
        :paramtype context: str
        :return: The XPIA score.
        :rtype: dict
        """
        return async_run_allowing_running_loop(self._async_evaluator, question=question, answer=answer, **kwargs)

    def _to_async(self):
        return self._async_evaluator
