# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

__path__ = __import__("pkgutil").extend_path(__path__, __name__)  # type: ignore

from promptflow import load_flow
from promptflow.entities import AzureOpenAIConnection
from pathlib import Path


def init(model_config: AzureOpenAIConnection, deployment_name: str):
    """
    Initialize an evaluation function configured for a specific Azure OpenAI model.

    :param model_config: Configuration for the Azure OpenAI model.
    :type model_config: AzureOpenAIConnection
    :param deployment_name: Deployment to be used which has Azure OpenAI model.
    :type deployment_name: AzureOpenAIConnection
    :return: A function that evaluates coherence.
    :rtype: function

    **Usage**

    .. code-block:: python

        eval_fn = coherence.init(model_config)
        result = eval_fn(
            question="What is the capital of Japan?",
            answer="The capital of Japan is Tokyo.")
    """
    def eval_fn(question: str, answer: str):

        # Load the flow as function
        current_dir = Path(__file__).resolve().parent
        flow_dir = current_dir / "flow"
        f = load_flow(source=flow_dir)

        # Override the connection
        f.context.connections = {
            "query_llm": {
                "connection": AzureOpenAIConnection(
                    api_base=model_config.api_base,
                    api_key=model_config.api_key,
                    api_version=model_config.api_version,
                    api_type="azure"
                ),
                "deployment_name": deployment_name,
            }
        }

        # Run the evaluation flow
        return f(question=question, answer=answer)

    return eval_fn