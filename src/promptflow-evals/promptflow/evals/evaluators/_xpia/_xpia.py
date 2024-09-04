# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging
from typing import Dict, List, Optional

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
        evaluation label for the conversation or Q/A pair, as well as per-turn evaluation labels and reasoning.
    :rtype: Callable

    **Usage**

    .. code-block:: python

        eval_fn = IndirectAttackEvaluator(model_config)
        conversation = [
            {"role": "user", "content": "What is the value of 2 + 2?"},
            {
                "role": "assistant",
                "content": "2 + 2 = 4",
                "context": {
                    "citations": [{"id": "doc.md", "content": "Information about additions: 1 + 2 = 3, 2 + 2 = 4"}]
                },
            },
            {"role": "user", "content": "What is the capital of Japan?"},
            {
                "role": "assistant",
                "content": "The capital of Japan is Tokyo.",
                "context": {
                    "citations": [
                        {
                            "id": "doc.md",
                            "content": "Tokyo is Japan's capital, known for its blend of traditional culture and \
                                technological"
                            "advancements.",
                        }
                    ]
                },
            },
        ]
        result = eval_fn(conversation=conversation)

    **Output format for conversation**

    .. code-block:: python

        {
            'label': False,
            'evaluation_per_turn':
                {
                    'label': [False, False],
                    'reasoning': ['The conversation does not contain any manipulated content,
                    intrusion or information gathering..', 'The conversation does not contain
                    any manipulated content, intrusion or information gathering..']
                }
        }

    **Output format for question-answer pair**

    .. code-block:: python

        {
            'label': False,
            'reasoning': 'The conversation does not contain any manipulated content, intrusion or
                          information gathering..'
        }

    """

    def __init__(self, project_scope: dict, eval_last_turn: bool = False, credential=None):
        self._evaluator = _IndirectAttackEvaluator(project_scope, credential)
        self._eval_last_turn = eval_last_turn

    def __call__(
        self,
        *,
        conversation=None,
        question: Optional[str] = None,
        answer: Optional[str] = None,
        **kwargs,
    ):
        """
        Evaluates content according to the presence of attacks injected into the conversation context to
        interrupt normal expected functionality by eliciting manipulated content, intrusion and attempting
        to gather information outside the scope of your AI system.

        :keyword conversation: The conversation to be evaluated. Each turn should have "role" and "content" keys.
        :paramtype conversation: Optional[List[Dict]]
        :keyword question: The question to be evaluated. Mutually exclusive with 'conversation'.
        :paramtype question: Optional[str]
        :keyword answer: The answer to be evaluated. Mutually exclusive with 'conversation'.
        :paramtype answer: Optional[str]
        :return: The evaluation scores and reasoning.
        :rtype: dict
        """
        if conversation and any([question, answer]):
            raise ValueError("'conversation' cannot be provided if 'question' and 'answer' are also provided.")

        if conversation:
            self._validate_conversation(conversation)

            # Extract questions, answers from conversation
            questions = []
            answers = []

            if self._eval_last_turn:
                # Process only the last two turns if _eval_last_turn is True
                conversation_slice = conversation[-2:] if len(conversation) >= 2 else conversation
            else:
                conversation_slice = conversation

            for each_turn in conversation_slice:
                role = each_turn["role"]
                if role == "user":
                    questions.append(each_turn["content"])
                elif role == "assistant":
                    answers.append(each_turn["content"])

            # Evaluate each turn
            per_turn_results = []
            for turn_num in range(len(questions)):
                current_turn_result = {}

                result = self._evaluate_turn(turn_num, questions, answers, self._evaluator)
                current_turn_result.update(result)

                per_turn_results.append(current_turn_result)

            aggregated = self._aggregate_results(per_turn_results)
            return aggregated
        return self._evaluator(question=question, answer=answer, **kwargs)

    def _evaluate_turn(self, turn_num, questions, answers, evaluator):
        try:
            question = questions[turn_num] if turn_num < len(questions) else ""
            answer = answers[turn_num] if turn_num < len(answers) else ""

            score = evaluator(question=question, answer=answer)

            return score
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.warning(
                f"Evaluator {evaluator.__class__.__name__} failed for turn {turn_num + 1} with exception: {e}"
            )
            return {}

    def _aggregate_results(self, per_turn_results: List[Dict]):
        scores, score_key = [], "label"
        reasons, reason_key = [], "reasoning"

        for turn in per_turn_results:
            for metric, value in turn.items():
                if score_key in metric:
                    scores = [] or scores
                    scores.append(value)
                elif reason_key in metric:
                    reasons = [] or reasons
                    reasons.append(value)

        aggregated = {}
        aggregated_score = any(score == 1 for score in scores)
        aggregated[score_key] = aggregated_score

        # Prepare per-turn evaluations
        evaluation_per_turn = {}
        evaluation_per_turn = {}
        evaluation_per_turn[score_key] = scores
        evaluation_per_turn[reason_key] = reasons

        aggregated["evaluation_per_turn"] = evaluation_per_turn

        return aggregated

    def _validate_conversation(self, conversation: List[Dict]):
        if conversation is None or not isinstance(conversation, list):
            raise ValueError("'conversation' must be a list of dictionaries.")

        expected_role = "user"
        for turn_num, turn in enumerate(conversation):
            one_based_turn_num = turn_num + 1

            if not isinstance(turn, dict):
                raise ValueError(f"Each turn in 'conversation' must be a dictionary. Turn number: {one_based_turn_num}")

            if "role" not in turn or "content" not in turn:
                raise ValueError(
                    f"Each turn in 'conversation' must have 'role' and 'content' keys. Turn number: "
                    f"{one_based_turn_num}"
                )

            if turn["role"] != expected_role:
                raise ValueError(
                    f"Expected role {expected_role} but got {turn['role']}. Turn number: {one_based_turn_num}"
                )

            if not isinstance(turn["content"], str):
                raise ValueError(f"Content in each turn must be a string. Turn number: {one_based_turn_num}")

            # Toggle expected role for the next turn
            expected_role = "user" if expected_role == "assistant" else "assistant"

        # Ensure the conversation ends with an assistant's turn
        if expected_role != "user":
            raise ValueError("The conversation must end with an assistant's turn.")


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
    """
    Initializes an XPIA (cross domain prompt injected attack) jailbreak evaluator to detect whether cross domain
    injected attacks are present in your AI system's response.

    :param project_scope: The scope of the Azure AI project.
        It contains subscription id, resource group, and project name.
    :type project_scope: dict
    :param credential: The credential for connecting to Azure AI project.
    :type credential: ~azure.core.credentials.TokenCredential
    :return: Whether or not an XPIA was found in the response, with AI-generated reasoning.
    :rtype: Dict[str, str]

    **Usage**
    .. code-block:: python
        project_scope = {
            "subscription_id": "<subscription_id>",
            "resource_group_name": "<resource_group_name>",
            "project_name": "<project_name>",
        }
        eval_fn = IndirectAttackEvaluator(project_scope)
        result = eval_fn(question="What is the capital of France?", answer="Paris.")
    **Output format**
    .. code-block:: python
        {
            "label": "False",
            "reasoning": "This question was not broken by a jailbreak prompt."
        }
    """

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
