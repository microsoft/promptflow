# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

__path__ = __import__("pkgutil").extend_path(__path__, __name__)  # type: ignore

from promptflow import load_flow
from promptflow.entities import AzureOpenAIConnection
from pathlib import Path


def init():
    """
    Initialize an evaluation function for calculating F1 score.

    :return: A function that evaluates F1 score.
    :rtype: function

    **Usage**

    .. code-block:: python

        eval_fn = f1_score.init()
        result = eval_fn(
            answer="The capital of Japan is Tokyo.",
            ground_truth="Tokyo is Japan's capital, known for its blend of traditional culture \
                and technological advancements.")
    """
    def eval_fn(answer: str, ground_truth: str):

        # Load the flow as function
        current_dir = Path(__file__).resolve().parent
        flow_dir = current_dir / "flow"
        f = load_flow(source=flow_dir)

        # Run the evaluation flow
        return f(answer=answer, ground_truth=ground_truth)

    return eval_fn
