# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os
import re

import numpy as np

from promptflow.client import load_flow
from promptflow.core import AzureOpenAIModelConfiguration
try:
    from ..._user_agent import USER_AGENT
except ImportError:
    USER_AGENT = None


class CoherenceEvaluator:
    """
    Initialize a coherence evaluator configured for a specific Azure OpenAI model.

    :param model_config: Configuration for the Azure OpenAI model.
    :type model_config: AzureOpenAIModelConfiguration

    **Usage**

    .. code-block:: python

        eval_fn = CoherenceEvaluator(model_config)
        result = eval_fn(
            question="What is the capital of Japan?",
            answer="The capital of Japan is Tokyo.")

    **Output format**

    .. code-block:: python

        {
            "gpt_coherence": 1.0
        }
    """

    def __init__(self, model_config: AzureOpenAIModelConfiguration):
        # TODO: Remove this block once the bug is fixed
        # https://msdata.visualstudio.com/Vienna/_workitems/edit/3151324
        if model_config.api_version is None:
            model_config.api_version = "2024-02-15-preview"

        prompty_model_config = {"configuration": model_config}
        prompty_model_config.update({"parameters": {"extra_headers": {"x-ms-useragent": USER_AGENT}}}) \
            if USER_AGENT and isinstance(model_config, AzureOpenAIModelConfiguration) else None

        current_dir = os.path.dirname(__file__)
        prompty_path = os.path.join(current_dir, "coherence.prompty")
        self._flow = load_flow(source=prompty_path, model=prompty_model_config)

    def __call__(self, *, question: str, answer: str, **kwargs):
        """
        Evaluate coherence.

        :param question: The question to be evaluated.
        :type question: str
        :param answer: The answer to be evaluated.
        :type answer: str
        :return: The coherence score.
        :rtype: dict
        """

        # Validate input parameters
        question = str(question or "")
        answer = str(answer or "")

        if not (question.strip() and answer.strip()):
            raise ValueError("Both 'question' and 'answer' must be non-empty strings.")

        # Run the evaluation flow
        llm_output = self._flow(question=question, answer=answer)

        score = np.nan
        if llm_output:
            match = re.search(r"\d", llm_output)
            if match:
                score = float(match.group())

        return {"gpt_coherence": float(score)}
