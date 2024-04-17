# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

__path__ = __import__("pkgutil").extend_path(__path__, __name__)  # type: ignore

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List

import numpy as np

from promptflow.evals.evaluators import CoherenceEvaluator, FluencyEvaluator, GroundednessEvaluator, RelevanceEvaluator

logger = logging.getLogger(__name__)


class ChatEvaluator:
    def __init__(
        self, model_config, eval_last_turn: bool = False, parallel: bool = True
    ):
        """
        Initialize an evaluator configured for a specific Azure OpenAI model.

        :param model_config: Configuration for the Azure OpenAI model.
        :type model_config: AzureOpenAIModelConfiguration
        :param eval_last_turn: Set to True to evaluate only the most recent exchange in the dialogue,
            focusing on the latest user inquiry and the assistant's corresponding response. Defaults to False
        :type eval_last_turn: bool
        :param parallel: If True, use parallel execution for evaluators. Else, use sequential execution.
            Default is True.
        :type parallel: bool
        :return: A function that evaluates and generates metrics for "chat" scenario.
        :rtype: function

        **Usage**

        .. code-block:: python

            eval_fn = ChatEvaluator(model_config)
            conversation = [
                {"role": "user", "content": "What is the value of 2 + 2?"},
                {"role": "assistant", "content": "2 + 2 = 4", "context": {
                    "citations": [
                            {"id": "math_doc.md", "content": "Information about additions: 1 + 2 = 3, 2 + 2 = 4"}
                            ]
                    }
                }
            ]
            result = chat_eval(conversation=conversation)
        """
        self._eval_last_turn = eval_last_turn
        self._parallel = parallel

        # TODO: Need a built-in evaluator for retrieval. It needs to be added to `self._rag_evaluators` collection
        self._rag_evaluators = [
            GroundednessEvaluator(model_config),
            RelevanceEvaluator(model_config),
        ]
        self._non_rag_evaluators = [
            CoherenceEvaluator(model_config),
            FluencyEvaluator(model_config),
        ]

    def __call__(self, *, conversation, **kwargs):
        """Evaluates chat scenario.

        :param conversation: The conversation to be evaluated. Each turn should have "role" and "content" keys.
            "context" key is optional for assistant's turn and should have "citations" key with list of citations.
        :type conversation: List[Dict]
        :return: The scores for Chat scenario.
        :rtype: dict
        """

        self._validate_conversation(conversation)

        # Extract questions, answers and contexts from conversation
        questions = []
        answers = []
        contexts = []

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
                if "context" in each_turn and "citations" in each_turn["context"]:
                    citations = json.dumps(each_turn["context"]["citations"])
                    contexts.append(citations)

        # Select evaluators to be used for evaluation
        compute_rag_based_metrics = True
        if len(answers) != len(contexts):
            safe_message = (
                "Skipping rag based metrics as we need citations or "
                "retrieved_documents in context key of every assistant's turn"
            )
            logger.warning(safe_message)
            compute_rag_based_metrics = False

        selected_evaluators = []
        selected_evaluators.extend(self._non_rag_evaluators)
        if compute_rag_based_metrics:
            selected_evaluators.extend(self._rag_evaluators)

        # Evaluate each turn
        per_turn_results = []
        for turn_num in range(len(questions)):
            current_turn_result = {}

            if self._parallel:
                # Parallel execution
                with ThreadPoolExecutor() as executor:
                    future_to_evaluator = {
                        executor.submit(
                            self._evaluate_turn, turn_num, questions, answers, contexts, evaluator
                        ): evaluator
                        for evaluator in selected_evaluators
                    }

                    for future in as_completed(future_to_evaluator):
                        result = future.result()
                        current_turn_result.update(result)
            else:
                # Sequential execution
                for evaluator in selected_evaluators:
                    result = self._evaluate_turn(turn_num, questions, answers, contexts, evaluator)
                    current_turn_result.update(result)

            per_turn_results.append(current_turn_result)

        # Aggregate results
        # Final aggregated results for a conversation will look like:
        #     "gpt_groundedness": 2.0, # Mean of all groundedness scores
        #     "evaluation_per_turn": {
        #         "gpt_groundedness": {
        #             "score": [1.0, ...],
        #             "reason": ["reason1", ...],
        #         },
        #     },
        # }
        aggregated = self._aggregate_results(per_turn_results)

        return aggregated

    def _evaluate_turn(self, turn_num, questions, answers, contexts, evaluator):
        try:
            question = questions[turn_num] if turn_num < len(questions) else ""
            answer = answers[turn_num] if turn_num < len(answers) else ""
            context = contexts[turn_num] if turn_num < len(contexts) else ""

            score = evaluator(question=question, answer=answer, context=context)

            return score
        except Exception as e:
            logger.warning(
                f"Evaluator {evaluator.__class__.__name__} failed for turn {turn_num + 1} with exception: {e}"
            )
            return {}

    def _aggregate_results(self, per_turn_results: List[Dict]):
        scores = {}
        reasons = {}

        for turn in per_turn_results:
            for metric, value in turn.items():
                if "reason" in metric:
                    if metric not in reasons:
                        reasons[metric] = []
                    reasons[metric].append(value)
                else:
                    if metric not in scores:
                        scores[metric] = []
                    scores[metric].append(value)

        aggregated = {}
        evaluation_per_turn = {}

        for metric, values in scores.items():
            aggregated[metric] = np.nanmean(values)

            # Prepare per-turn evaluations
            evaluation_per_turn[metric] = {"score": values}
            reason_key = f"{metric}_reason"
            if reason_key in reasons:
                evaluation_per_turn[metric]["reason"] = reasons[reason_key]

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

            if turn["role"] == "assistant" and "context" in turn:
                if not isinstance(turn["context"], dict):
                    raise ValueError(
                        f"Context in each assistant's turn must be a dictionary. Turn number: {one_based_turn_num}"
                    )

                if "citations" not in turn["context"]:
                    raise ValueError(
                        f"Context in each assistant's turn must have 'citations' key. Turn number:"
                        f" {one_based_turn_num}"
                    )

                if not isinstance(turn["context"]["citations"], list):
                    raise ValueError(f"'citations' in context must be a list. Turn number: {one_based_turn_num}")

                for citation_num, citation in enumerate(turn["context"]["citations"]):
                    if not isinstance(citation, dict):
                        raise ValueError(
                            f"Each citation in 'citations' must be a dictionary. Turn number: {one_based_turn_num},"
                            f" Citation number: {citation_num + 1}"
                        )

            # Toggle expected role for the next turn
            expected_role = "user" if expected_role == "assistant" else "assistant"

        # Ensure the conversation ends with an assistant's turn
        if expected_role != "user":
            raise ValueError("The conversation must end with an assistant's turn.")
