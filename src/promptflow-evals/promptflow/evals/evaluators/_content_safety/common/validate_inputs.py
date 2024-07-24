# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from promptflow.core import tool


@tool
def validate_inputs(question: str, answer: str) -> bool:
    """Validate input parameters for content safety evaluation.

    :param question: The question to be evaluated.
    :type question: str
    :param answer: The answer to be evaluated.
    :type answer: str
    :raises ValueError: If input parameters are invalid.
    :return: True if input parameters are valid.
    :rtype: bool
    """
    # Validate input parameters
    if not (question and question.strip() and question != "None") or not (
        answer and answer.strip() and answer != "None"
    ):
        raise ValueError("Both 'question' and 'answer' must be non-empty strings.")

    return True
