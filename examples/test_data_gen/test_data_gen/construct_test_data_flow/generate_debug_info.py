from utils import ValidateObj, ValidationResult

from promptflow import tool


# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need
@tool
def my_python_tool(
    question_type: str,
    text_trunk: str,
    text_meta: dict = None,
    validate_and_generate_seed_question_output: dict = None,
    validate_and_generate_test_question_output: dict = None,
    validate_ground_truth_output: ValidationResult = None,
) -> dict:
    text_trunk_validation_res = validate_and_generate_seed_question_output["validation_res"]
    generated_seed_question = validate_and_generate_seed_question_output["question"]
    seed_question_validation_res = validate_and_generate_test_question_output["validation_res"]
    generated_ground_truth = validate_ground_truth_output["ground_truth"]
    ground_truth_validation_res = validate_ground_truth_output["validation_res"]

    is_generation_success = generated_ground_truth != ""
    is_text_trunk_valid = text_trunk_validation_res.pass_validation if text_trunk_validation_res else None
    is_seed_question_valid = seed_question_validation_res.pass_validation if seed_question_validation_res else None
    is_ground_truth_valid = ground_truth_validation_res.pass_validation if ground_truth_validation_res else None

    failed_step = ""
    failed_reason = ""
    if not is_generation_success:
        if is_text_trunk_valid is False:
            failed_step = ValidateObj.TEXT_TRUNK
            failed_reason = text_trunk_validation_res.reason_if_failed
        elif is_seed_question_valid is False:
            failed_step = ValidateObj.QUESTION
            failed_reason = seed_question_validation_res.reason_if_failed
        elif is_ground_truth_valid is False:
            failed_step = ValidateObj.GROUND_TRUTH
            failed_reason = ground_truth_validation_res.reason_if_failed

    return {
        "question_type": question_type,
        "text_trunk": text_trunk,
        "text_meta": text_meta,
        "generation_summary": {
            "success": is_generation_success,
            "failed_step": failed_step,
            "failed_reason": failed_reason,
        },
        "generation_details": {
            "text_trunk": {
                "pass_validation": is_text_trunk_valid,
                "reason_if_failed": text_trunk_validation_res.reason_if_failed
                if is_text_trunk_valid is False
                else None,
            },
            "seed_question": {
                "generated_question": generated_seed_question,
                "pass_validation": is_seed_question_valid,
                "reason_if_failed": seed_question_validation_res.reason_if_failed
                if is_seed_question_valid is False
                else None,
            },
            # "test_question": {},  # placeholder for evolved questions like multi-context, reasoning, etc.
            "ground_truth": {
                "generated_ground_truth": generated_ground_truth,
                "pass_validation": is_ground_truth_valid,
                "reason_if_failed": ground_truth_validation_res.reason_if_failed
                if is_ground_truth_valid is False
                else None,
            },
        },
    }
