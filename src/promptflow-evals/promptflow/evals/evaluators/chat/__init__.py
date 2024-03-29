# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

__path__ = __import__("pkgutil").extend_path(__path__, __name__)  # type: ignore

from promptflow.entities import AzureOpenAIConnection
from promptflow.evals.evaluators import GroundednessEvaluator, RelevanceEvaluator, CoherenceEvaluator, FluencyEvaluator
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import logging
import numpy as np


logger = logging.getLogger(__name__)


class ChatEvaluator:
    def __init__(self, model_config: AzureOpenAIConnection, deployment_name: str):
        """
        Initialize an evaluator configured for a specific Azure OpenAI model.

        :param model_config: Configuration for the Azure OpenAI model.
        :type model_config: AzureOpenAIConnection
        :param deployment_name: Deployment to be used which has Azure OpenAI model.
        :type deployment_name: AzureOpenAIConnection
        :return: A function that evaluates and generates metrics for "chat" scenario.
        :rtype: function

        **Usage**

        .. code-block:: python

            eval_fn = ChatEvaluator(model_config, deployment_name="gpt-4")
            conversation = [
                {"role": "user", "content": "What is the value of 2 + 2?"},
                {"role": "assistant", "content": "2 + 2 = 4", "context": {
                    "citations": [{"id": "math_doc.md", "content": "Information about additions: 1 + 2 = 3, 2 + 2 = 4"}]}}
            ]
            result = chat_eval(conversation=conversation)
        """

        # TODO: Need a built-in evaluator for retrieval. It needs to be added to `self._rag_evaluators` collection
        self._rag_evaluators  = [
            GroundednessEvaluator(model_config, deployment_name=deployment_name),
            RelevanceEvaluator(model_config, deployment_name=deployment_name),
        ]
        self._non_rag_evaluators = [
            CoherenceEvaluator(model_config, deployment_name=deployment_name),
            FluencyEvaluator(model_config, deployment_name=deployment_name),
        ]

    def __call__(self, *, conversation: List[Dict], parallel=True, **kwargs):
        """Evaluates chat scenario.

        :param conversation: The conversation to be evaluated. Each turn should have "role" and "content" keys.
                             "context" key is optional for assistant's turn and should have "citations" key with list of citations.
        :type conversation: List[Dict]
        :param parallel: If True, use parallel execution for evaluators. Else, use sequential execution. Default is True.
        :type parallel: bool
        :return: The scores for Chat scenario.
        :rtype: dict
        """

        self._validate_conversation(conversation)

        # Extract questions, answers and contexts from conversation
        questions = []
        answers = []
        contexts = []
        for turn_num, each_turn in enumerate(conversation):
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
            safe_message = "Skipping rag based metrics as we need citations or " \
                            "retrieved_documents in context key of every assistant's turn"
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

            if parallel:
                # Parallel execution
                with ThreadPoolExecutor() as executor:
                    future_to_evaluator = {
                        executor.submit(self._evaluate_turn, turn_num, questions, answers, contexts, evaluator): evaluator
                        for evaluator in selected_evaluators
                    }

                    for future in as_completed(future_to_evaluator):
                        score = future.result()
                        current_turn_result.update(score)
            else:
                # Sequential execution
                for evaluator in selected_evaluators:
                    score = self._evaluate_turn(turn_num, questions, answers, contexts, evaluator)
                    current_turn_result.update(score)

            per_turn_results.append(current_turn_result)

        # Aggregate results
        # Final aggregated results for a conversation will look like:
        # {
        #     "gpt_groundedness": 0.9,
        #     "gpt_groundedness_per_turn": [0.9, 0.8, 0.9, ...],
        #     ...
        # }
        aggregated = {}
        for key in per_turn_results[0].keys():
            values = [d[key] for d in per_turn_results]
            aggregated[key] = np.nanmean(values)
            aggregated[key + "_per_turn"] = values

        return aggregated

    def _evaluate_turn(self, turn_num, questions, answers, contexts, evaluator):
        try:
            question = questions[turn_num] if turn_num < len(questions) else ""
            answer = answers[turn_num] if turn_num < len(answers) else ""
            context = contexts[turn_num] if turn_num < len(contexts) else ""

            score = evaluator(
                question=question,
                answer=answer,
                context=context)

            return score
        except Exception as e:
            logger.warning(f"Evaluator {evaluator.__class__.__name__} failed for turn {turn_num + 1} with exception: {e}")
            return {}

    def _validate_conversation(self, conversation: List[Dict]):
        if conversation is None or not isinstance(conversation, list):
            raise ValueError("'conversation' must be a list of dictionaries.")

        expected_role = "user"
        for turn_num, turn in enumerate(conversation):
            one_based_turn_num = turn_num + 1

            if not isinstance(turn, dict):
                raise ValueError(f"Each turn in 'conversation' must be a dictionary. Turn number: {one_based_turn_num}")

            if "role" not in turn or "content" not in turn:
                raise ValueError(f"Each turn in 'conversation' must have 'role' and 'content' keys. Turn number: {one_based_turn_num}")

            if turn["role"] != expected_role:
                raise ValueError(f"Expected role {expected_role} but got {turn['role']}. Turn number: {one_based_turn_num}")

            if not isinstance(turn["content"], str):
                raise ValueError(f"Content in each turn must be a string. Turn number: {one_based_turn_num}")

            if turn["role"] == "assistant" and "context" in turn:
                if not isinstance(turn["context"], dict):
                    raise ValueError(f"Context in each assistant's turn must be a dictionary. Turn number: {one_based_turn_num}")

                if "citations" not in turn["context"]:
                    raise ValueError(f"Context in each assistant's turn must have 'citations' key. Turn number: {one_based_turn_num}")

                if not isinstance(turn["context"]["citations"], list):
                    raise ValueError(f"'citations' in context must be a list. Turn number: {one_based_turn_num}")

                for citation_num, citation in enumerate(turn["context"]["citations"]):
                    if not isinstance(citation, dict):
                        raise ValueError(f"Each citation in 'citations' must be a dictionary. Turn number: {one_based_turn_num}, Citation number: {citation_num + 1}")

            # Toggle expected role for the next turn
            expected_role = "user" if expected_role == "assistant" else "assistant"

        # Ensure the conversation ends with an assistant's turn
        if expected_role != "user":
            raise ValueError("The conversation must end with an assistant's turn.")
