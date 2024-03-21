# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

__path__ = __import__("pkgutil").extend_path(__path__, __name__)  # type: ignore

from promptflow import load_flow
from promptflow.entities import AzureOpenAIConnection
from pathlib import Path


class F1ScoreEvaluator:
    """
        Initialize an evaluation function for calculating F1 score.

        :return: A function that evaluates F1 score.
        :rtype: function

        **Usage**

        .. code-block:: python

            eval_fn = F1ScoreEvaluator()
            result = eval_fn(
                answer="The capital of Japan is Tokyo.",
                ground_truth="Tokyo is Japan's capital, known for its blend of traditional culture \
                    and technological advancements.")
        """
    def __init__(self):
        self._flow = self._init_flow()

    def _init_flow(self):
        # Load the flow as function
        current_dir = Path(__file__).resolve().parent
        flow_dir = current_dir / "flow"
        f = load_flow(source=flow_dir)
        return f

    def __call__(self, answer: str, ground_truth: str):
        return self._flow(answer=answer, ground_truth=ground_truth)
