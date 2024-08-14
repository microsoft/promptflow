# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os
import re
from typing import Union

import numpy as np

from promptflow._utils.async_utils import async_run_allowing_running_loop
from promptflow.core import AsyncPrompty, AzureOpenAIModelConfiguration, OpenAIModelConfiguration

try:
    from ..._user_agent import USER_AGENT
except ImportError:
    USER_AGENT = None


class _AsyncGroundednessEvaluator:
    # Constants must be defined within eval's directory to be save/loadable
    PROMPTY_FILE = "groundedness.prompty"
    LLM_CALL_TIMEOUT = 600
    DEFAULT_OPEN_API_VERSION = "2024-02-15-preview"

    def __init__(self, model_config: Union[AzureOpenAIModelConfiguration, OpenAIModelConfiguration]):
        if (
            isinstance(model_config, AzureOpenAIModelConfiguration)
            and (not hasattr(model_config, "api_version") or model_config.api_version) is None
        ):
            model_config.api_version = self.DEFAULT_OPEN_API_VERSION

        prompty_model_config = {"configuration": model_config, "parameters": {"extra_headers": {}}}

        # Handle "RuntimeError: Event loop is closed" from httpx AsyncClient
        # https://github.com/encode/httpx/discussions/2959
        prompty_model_config["parameters"]["extra_headers"].update({"Connection": "close"})

        if USER_AGENT and isinstance(model_config, AzureOpenAIModelConfiguration):
            prompty_model_config["parameters"]["extra_headers"].update({"x-ms-useragent": USER_AGENT})

        current_dir = os.path.dirname(__file__)
        prompty_path = os.path.join(current_dir, "groundedness.prompty")
        self._flow = AsyncPrompty.load(source=prompty_path, model=prompty_model_config)

    async def __call__(self, *, answer: str, context: str, **kwargs):
        # Validate input parameters
        answer = str(answer or "")
        context = str(context or "")

        if not answer.strip() or not context.strip():
            raise ValueError("Both 'answer' and 'context' must be non-empty strings.")

        # Run the evaluation flow
        llm_output = await self._flow(answer=answer, context=context, timeout=self.LLM_CALL_TIMEOUT, **kwargs)

        score = np.nan
        if llm_output:
            match = re.search(r"\d", llm_output)
            if match:
                score = float(match.group())

        return {"gpt_groundedness": float(score)}


class GroundednessEvaluator:
    """
    Initialize a groundedness evaluator configured for a specific Azure OpenAI model.

    :param model_config: Configuration for the Azure OpenAI model.
    :type model_config: Union[~promptflow.core.AzureOpenAIModelConfiguration,
        ~promptflow.core.OpenAIModelConfiguration]

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

    def __init__(self, model_config: Union[AzureOpenAIModelConfiguration, OpenAIModelConfiguration]):
        self._async_evaluator = _AsyncGroundednessEvaluator(model_config)

    def __call__(self, *, answer: str, context: str, **kwargs):
        """
        Evaluate groundedness of the answer in the context.

        :keyword answer: The answer to be evaluated.
        :paramtype answer: str
        :keyword context: The context in which the answer is evaluated.
        :paramtype context: str
        :return: The groundedness score.
        :rtype: dict
        """
        return async_run_allowing_running_loop(self._async_evaluator, answer=answer, context=context, **kwargs)

    def _to_async(self):
        return self._async_evaluator
