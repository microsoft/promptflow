# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os
import re

import numpy as np

from promptflow.client import load_flow
from promptflow.core import AzureOpenAIModelConfiguration

logger = logging.getLogger(__name__)


class GroundednessEvaluator:
    def __init__(self, model_config: AzureOpenAIModelConfiguration = None, project_scope: dict = None, credential=None):
        """
        Initialize an evaluator configured for a specific Azure OpenAI model.

        :param model_config: Configuration for the Azure OpenAI model.
        :type model_config: AzureOpenAIModelConfiguration
        :param project_scope: The scope of the Azure AI project.
            It contains subscription id, resource group, and project name.
        :type project_scope: dict
        :param credential: The credential for connecting to Azure AI project.
        :type credential: TokenCredential

        **Usage**

        .. code-block:: python

            eval_fn = GroundednessEvaluator(model_config)
            result = eval_fn(
                answer="The capital of Japan is Tokyo.",
                context="Tokyo is Japan's capital, known for its blend of traditional culture \
                    and technological advancements.")
        """
        if not model_config and not project_scope:
            raise ValueError("Either 'model_config' or 'project_scope' must be provided.")

        self._model_config = model_config
        self._project_scope = project_scope

        if model_config:
            # TODO: Remove this block once the bug is fixed
            # https://msdata.visualstudio.com/Vienna/_workitems/edit/3151324
            if model_config.api_version is None:
                model_config.api_version = "2024-02-15-preview"

            prompty_model_config = {"configuration": model_config}
            current_dir = os.path.dirname(__file__)
            prompty_path = os.path.join(current_dir, "groundedness.prompty")
            self._prompty_flow = load_flow(source=prompty_path, model=prompty_model_config)

        if self._project_scope:
            self._credential = credential
            current_dir = os.path.dirname(__file__)
            service_flow_path = os.path.join(current_dir, "flow")
            self._service_flow = load_flow(source=service_flow_path)

    def __call__(self, *, answer: str, context: str, question: str = None, **kwargs):
        """Evaluate groundedness of the answer in the context.

        :param answer: The answer to be evaluated.
        :type answer: str
        :param context: The context in which the answer is evaluated.
        :type context: str
        :param question: The question for which the answer is provided.
        :type question: str
        :return: The groundedness score.
        :rtype: dict
        """
        # Validate input parameters
        answer = str(answer or "")
        context = str(context or "")
        question = str(question or "")

        if not (answer.strip()) or not (context.strip()):
            raise ValueError("Both 'answer' and 'context' must be non-empty strings.")

        if self._project_scope:
            try:
                output = self._service_flow(
                    question=question,
                    answer=answer,
                    context=context,
                    project_scope=self._project_scope,
                    credential=self._credential,
                )
                if output:
                    # TODO: Include the reason in the result
                    return {"gpt_groundedness": float(output["result"]["label"])}
            except Exception as e:
                logger.warning(f"Failed to evaluate groundedness using service: {e}. Falling back to prompty.")
                pass

        if self._model_config:
            llm_output = self._prompty_flow(answer=answer, context=context)

            score = np.nan
            if llm_output:
                match = re.search(r"\d", llm_output)
                if match:
                    score = float(match.group())

            return {"gpt_groundedness": float(score)}

        return {"gpt_groundedness": np.nan}
