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


class GroundednessEvaluator:
    """
    Initialize a groundedness evaluator configured for a specific Azure OpenAI model.

    :param model_config: Configuration for the Azure OpenAI model.
    :type model_config: AzureOpenAIModelConfiguration

    **Usage**

    .. code-block:: python

        eval_fn = GroundednessEvaluator(model_config)
        result = eval_fn(
            answer="The capital of Japan is Tokyo.",
            context="Tokyo is Japan's capital, known for its blend of traditional culture \
                and technological advancements.")

    **Output format**

    .. code-block:: python

        {
            "gpt_groundedness": 5
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
        prompty_path = os.path.join(current_dir, "groundedness.prompty")
        self._flow = load_flow(source=prompty_path, model=prompty_model_config)

    def __call__(self, *, answer: str, context: str, **kwargs):
        """
        Evaluate groundedness of the answer in the context.

        :param answer: The answer to be evaluated.
        :type answer: str
        :param context: The context in which the answer is evaluated.
        :type context: str
        :return: The groundedness score.
        :rtype: dict
        """
        # Validate input parameters
        answer = str(answer or "")
        context = str(context or "")

        if not (answer.strip()) or not (context.strip()):
            raise ValueError("Both 'answer' and 'context' must be non-empty strings.")

        # Run the evaluation flow
        llm_output = self._flow(answer=answer, context=context)

        score = np.nan
        if llm_output:
            match = re.search(r"\d", llm_output)
            if match:
                score = float(match.group())

        return {"gpt_groundedness": float(score)}
