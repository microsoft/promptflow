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

    **Usage**

    .. code-block:: python

        eval_fn = qa.init(model_config)
        result = qa_eval(
        question="Tokyo is the capital of which country?",
        answer="Japan",
        context="Tokyo is the capital of Japan.",
        ground_truth="Japan",
    )
    """

    def eval_fn(*, answer: str, question: str = None, context: str = None, ground_truth: str = None, **kwargs):
        # TODO: How to parallelize metrics calculation
        from promptflow.evals.evaluators import groundedness, f1_score

        groundedness_eval = groundedness.init(model_config)
        f1_score_eval = f1_score.init()

        return{
            **groundedness_eval(answer=answer, context=context),
            **f1_score_eval(answer=answer, ground_truth=ground_truth)
        }

    return eval_fn
