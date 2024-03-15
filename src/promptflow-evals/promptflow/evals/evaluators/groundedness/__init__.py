# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

__path__ = __import__("pkgutil").extend_path(__path__, __name__)  # type: ignore

from promptflow import load_flow
from promptflow.entities import AzureOpenAIConnection
from pathlib import Path


def init(model_config: AzureOpenAIConnection):
    """
    Initialize an evaluation function configured for a specific Azure OpenAI model.

    :param model_config: Configuration for the Azure OpenAI model.
    :type model_config: AzureOpenAIConnection
    :return: A function that evaluates groundedness.
    :rtype: function
    :raises ValueError: If any input parameter is an empty string.

    **Usage**

    .. code-block:: python

        eval_fn = groundedness.init(model_config)
        result = eval_fn(
            answer="The capital of Japan is Tokyo.", 
            context="Tokyo is Japan's capital, known for its blend of traditional culture \
                and technological advancements.")
    """
    def eval_fn(answer: str, context: str):
        # Validate input parameters
        if not (answer and answer.strip()) or not (context and context.strip()):
            raise ValueError("Both 'answer' and 'context' must be non-empty strings.")
    
        # Load the flow as function
        current_dir = Path(__file__).resolve().parent
        flow_dir = current_dir / "flow"
        f = load_flow(source=flow_dir)

        # connection = AzureOpenAIConnection(
        #     name="open_ai_connection",
        #     api_key=model_config.api_key,
        #     api_base=model_config.api_base,
        #     api_type="azure",
        #     api_version=model_config.api_version,
        #     model_name=model_config.model_name,
        #     deployment_name=model_config.deployment_name,
        # )
        
        f.context.connections = { 
            "query_llm": { "connection": model_config } 
        }

        # Run the evaluation flow
        return f(answer=answer, context=context)
    return eval_fn
    