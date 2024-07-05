# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from .flow.f1_score import compute_f1_score
from .flow.validate_inputs import validate_inputs

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
        pass # no init work needed.

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

        # Validate inputs
        # Raises value error if failed, so execution alone signifies success.
        _ = validate_inputs(answer=answer, ground_truth=ground_truth)

        # Run f1 score computation.
        f1_result = compute_f1_score(answer=answer, ground_truth=ground_truth)

        return {"f1_score": f1_result}
