from promptflow import load_flow
from pathlib import Path
from azure.core.credentials import TokenCredential
from promptflow.evals._constants import EvaluationMetrics


def init(project_scope: dict, credential: TokenCredential):
    """
    Initialize an evaluation function configured for a specific Azure OpenAI model.

    :param model_config: Configuration for the Azure OpenAI model.
    :type model_config: AzureOpenAIConnection
    :return: A function that evaluates self harm.
    :rtype: function

    **Usage**

    .. code-block:: python

        eval_fn = self_harm.init(model_config)
        result = eval_fn(question="What is the capital of France?", answer="Paris.")
    """

    # Load the flow as function
    current_dir = Path(__file__).resolve().parent
    flow_dir = current_dir / "flow"
    f = load_flow(source=flow_dir)

    def eval_fn(question: str, answer: str):

        # Run the evaluation flow
        output = f(
            metric_name=EvaluationMetrics.SELF_HARM,
            question=question,
            answer=answer,
            project_scope=project_scope,
            credential=credential)

        return output["result"]

    return eval_fn