# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import logging
import os
import re

import numpy as np

from promptflow.client import load_flow
from promptflow.core import AzureOpenAIModelConfiguration

logger = logging.getLogger(__name__)


class RetrievalChatEvaluator:
    """
    Initialize an evaluator configured for a specific Azure OpenAI model.

    :param model_config: Configuration for the Azure OpenAI model.
    :type model_config: AzureOpenAIModelConfiguration
    :return: A function that evaluates and generates metrics for "chat" scenario.
    :rtype: function
    **Usage**

    .. code-block:: python

        chat_eval = RetrievalChatEvaluator(model_config)
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

    **Output format**

    .. code-block:: python

    {
        "gpt_retrieval": 3.0
        "evaluation_per_turn": {
            "gpt_retrieval": {
                "score": [1.0, 2.0, 3.0]
            }
        }
    }
    """

    def __init__(self, model_config: AzureOpenAIModelConfiguration):
        # TODO: Remove this block once the bug is fixed
        # https://msdata.visualstudio.com/Vienna/_workitems/edit/3151324
        if model_config.api_version is None:
            model_config.api_version = "2024-02-15-preview"

        prompty_model_config = {"configuration": model_config}
        current_dir = os.path.dirname(__file__)
        prompty_path = os.path.join(current_dir, "retrieval.prompty")
        self._flow = load_flow(source=prompty_path, model=prompty_model_config)

    def __call__(self, *, conversation, **kwargs):
        """Evaluates retrieval score chat scenario.

        :param conversation: The conversation to be evaluated.
        :type conversation: List[Dict]
        :return: The scores for Chat scenario.
        :rtype: dict
        """
        # Extract questions, answers and contexts from conversation
        questions = []
        answers = []
        contexts = []

        for each_turn in conversation:
            role = each_turn["role"]
            if role == "user":
                questions.append(each_turn["content"])
            elif role == "assistant":
                answers.append(each_turn["content"])
                if "context" in each_turn and "citations" in each_turn["context"]:
                    citations = json.dumps(each_turn["context"]["citations"])
                    contexts.append(citations)

        # Evaluate each turn
        per_turn_scores = []
        history = []
        for turn_num in range(len(questions)):
            try:
                question = questions[turn_num] if turn_num < len(questions) else ""
                answer = answers[turn_num] if turn_num < len(answers) else ""
                context = contexts[turn_num] if turn_num < len(contexts) else ""

                history.append({"user": question, "assistant": answer})

                llm_output = self._flow(query=question, history=history, documents=context)
                score = np.nan
                if llm_output:
                    parsed_score_response = re.findall(r"\d+", llm_output.split("# Result")[-1].strip())
                    if len(parsed_score_response) > 0:
                        score = float(parsed_score_response[0].replace("'", "").strip())

                per_turn_scores.append(score)

            except Exception as e:
                logger.warning(
                    f"Evaluator {self.__class__.__name__} failed for turn {turn_num + 1} with exception: {e}"
                )

                per_turn_scores.append(np.nan)

        return {
            "gpt_retrieval": np.nanmean(per_turn_scores),
            "evaluation_per_turn": {
                "gpt_retrieval": {
                    "score": per_turn_scores,
                }
            },
        }
