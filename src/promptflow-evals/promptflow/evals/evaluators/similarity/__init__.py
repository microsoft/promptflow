# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

__path__ = __import__("pkgutil").extend_path(__path__, __name__)  # type: ignore

from pathlib import Path

from promptflow.client import load_flow
from promptflow.core._prompty_utils import convert_model_configuration_to_connection


class SimilarityEvaluator:
    def __init__(self, model_config):
        """
        Initialize an evaluator configured for a specific Azure OpenAI model.

        :param model_config: Configuration for the Azure OpenAI model.
        :type model_config: AzureOpenAIModelConfiguration

        **Usage**

        .. code-block:: python

            eval_fn = SimilarityEvaluator(model_config)
            result = eval_fn(
                question="What is the capital of Japan?",
                answer="The capital of Japan is Tokyo.",
                ground_truth="Tokyo is Japan's capital.")
        """

        # Load the flow as function
        current_dir = Path(__file__).resolve().parent
        flow_dir = current_dir / "flow"
        self._flow = load_flow(source=flow_dir)

        # Override the connection
        connection = convert_model_configuration_to_connection(model_config)
        self._flow.context.connections = {
            "query_llm": {
                "connection": connection,
                "deployment_name": model_config.azure_deployment,
            }
        }

    def __call__(self, *, question: str, answer: str, ground_truth: str, **kwargs):
        """Evaluate similarity.

        :param question: The question to be evaluated.
        :type question: str
        :param answer: The answer to be evaluated.
        :type answer: str
        :param ground_truth: The ground truth to be evaluated.
        :type ground_truth: str
        :return: The similarity score.
        :rtype: dict
        """

        # Run the evaluation flow
        return self._flow(question=question, answer=answer, ground_truth=ground_truth)
