from typing import Union

from utils import ErrorMsg, get_ground_truth_validation_res

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
):
    """
    1. Validates the given ground truth.

    Returns:
        dict: The generated ground truth and its validation result.
    """
    if not ground_truth:
        return {"ground_truth": "", "validation_res": None}

    validation_res = get_ground_truth_validation_res(connection, model, validate_ground_truth_prompt, ground_truth)
    is_valid_gt = validation_res.pass_validation
    failed_reason = ""
    if not is_valid_gt:
        failed_reason = ErrorMsg.INVALID_ANSWER.format(ground_truth)
        print(failed_reason)
        ground_truth = ""

    return {"ground_truth": ground_truth, "validation_res": validation_res}
