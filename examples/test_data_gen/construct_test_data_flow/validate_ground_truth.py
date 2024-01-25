from typing import Union

from utils import is_valid_ground_truth

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection


# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need
@tool
def validate_ground_truth(
    connection: Union[OpenAIConnection, AzureOpenAIConnection],
    model: str,
    ground_truth: str,
    validate_ground_truth_prompt: str,
) -> str:
    """
    1. Validates the given ground truth.

    Returns:
        str: The validated ground truth.
    """
    if not ground_truth:
        return ""

    is_valid_gt = is_valid_ground_truth(connection, model, validate_ground_truth_prompt, ground_truth)
    if not is_valid_gt:
        print(f"Invalid ground truth: {ground_truth}")
        return ""
    else:
        return ground_truth
