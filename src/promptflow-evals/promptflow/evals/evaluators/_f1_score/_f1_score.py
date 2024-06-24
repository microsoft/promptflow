# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path

from promptflow.client import load_flow


class F1ScoreEvaluator:
    """
    Initialize a f1 score evaluator for calculating F1 score.

    **Usage**

    .. code-block:: python

        eval_fn = F1ScoreEvaluator()
        result = eval_fn(
            answer="The capital of Japan is Tokyo.",
            ground_truth="Tokyo is Japan's capital, known for its blend of traditional culture \
                and technological advancements.")

    **Output format**

    .. code-block:: python

        {
            "f1_score": 0.42
        }
    """

    def __init__(self):
        # Load the flow as function
        current_dir = Path(__file__).resolve().parent
        flow_dir = current_dir / "flow"
        self._flow = load_flow(source=flow_dir)

    def __call__(self, *, answer: str, ground_truth: str, **kwargs):
        """
        Evaluate F1 score.

        :param answer: The answer to be evaluated.
        :type answer: str
        :param ground_truth: The ground truth to be evaluated.
        :type ground_truth: str
        :return: The F1 score.
        :rtype: dict
        """

        # Run the evaluation flow
        return self._flow(answer=answer, ground_truth=ground_truth)
