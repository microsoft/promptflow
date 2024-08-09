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


class _AsyncSimilarityEvaluator:
    # Constants must be defined within eval's directory to be save/loadable
    PROMPTY_FILE = "similarity.prompty"
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
        prompty_path = os.path.join(current_dir, self.PROMPTY_FILE)
        self._flow = AsyncPrompty.load(source=prompty_path, model=prompty_model_config)

    async def __call__(self, *, question: str, answer: str, ground_truth: str, **kwargs):
        # Validate input parameters
        question = str(question or "")
        answer = str(answer or "")
        ground_truth = str(ground_truth or "")

        if not (question.strip() and answer.strip() and ground_truth.strip()):
            raise ValueError("'question', 'answer' and 'ground_truth' must be non-empty strings.")

        # Run the evaluation flow
        llm_output = await self._flow(
            question=question, answer=answer, ground_truth=ground_truth, timeout=self.LLM_CALL_TIMEOUT, **kwargs
        )

        score = np.nan
        if llm_output:
            match = re.search(r"\d", llm_output)
            if match:
                score = float(match.group())

        return {"gpt_similarity": float(score)}


class SimilarityEvaluator:
    """
    Initialize a similarity evaluator configured for a specific Azure OpenAI model.

    :param model_config: Configuration for the Azure OpenAI model.
    :type model_config: Union[~promptflow.core.AzureOpenAIModelConfiguration,
        ~promptflow.core.OpenAIModelConfiguration]

    **Usage**

    .. code-block:: python

        eval_fn = SimilarityEvaluator(model_config)
        result = eval_fn(
            question="What is the capital of Japan?",
            answer="The capital of Japan is Tokyo.",
            ground_truth="Tokyo is Japan's capital.")

    **Output format**

    .. code-block:: python

        {
            "gpt_similarity": 3.0
        }
    """

    def __init__(self, model_config: Union[AzureOpenAIModelConfiguration, OpenAIModelConfiguration]):
        self._async_evaluator = _AsyncSimilarityEvaluator(model_config)

    def __call__(self, *, question: str, answer: str, ground_truth: str, **kwargs):
        """
        Evaluate similarity.

        :keyword question: The question to be evaluated.
        :paramtype question: str
        :keyword answer: The answer to be evaluated.
        :paramtype answer: str
        :keyword ground_truth: The ground truth to be evaluated.
        :paramtype ground_truth: str
        :return: The similarity score.
        :rtype: dict
        """
        return async_run_allowing_running_loop(
            self._async_evaluator, question=question, answer=answer, ground_truth=ground_truth, **kwargs
        )

    def _to_async(self):
        return self._async_evaluator
