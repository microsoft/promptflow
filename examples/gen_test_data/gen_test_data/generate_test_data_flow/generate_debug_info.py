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
    validate_suggested_answer_output: ValidationResult = None,
) -> dict:
    text_trunk_validation_res = validate_and_generate_seed_question_output["validation_res"]
    generated_seed_question = validate_and_generate_seed_question_output["question"]
    seed_question_validation_res = validate_and_generate_test_question_output["validation_res"]
    generated_suggested_answer = validate_suggested_answer_output["suggested_answer"]
    suggested_answer_validation_res = validate_suggested_answer_output["validation_res"]

    is_generation_success = generated_suggested_answer != ""
    is_text_trunk_valid = text_trunk_validation_res.pass_validation if text_trunk_validation_res else None
    is_seed_question_valid = seed_question_validation_res.pass_validation if seed_question_validation_res else None
    is_suggested_answer_valid = (
        suggested_answer_validation_res.pass_validation if suggested_answer_validation_res else None
    )

    failed_step = ""
    failed_reason = ""
    if not is_generation_success:
        if is_text_trunk_valid is False:
            failed_step = ValidateObj.TEXT_TRUNK
            failed_reason = text_trunk_validation_res.reason
        elif is_seed_question_valid is False:
            failed_step = ValidateObj.QUESTION
            failed_reason = seed_question_validation_res.reason
        elif is_suggested_answer_valid is False:
            failed_step = ValidateObj.SUGGESTED_ANSWER
            failed_reason = suggested_answer_validation_res.reason

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
                "score": text_trunk_validation_res.score if text_trunk_validation_res else None,
                "reason": text_trunk_validation_res.reason if text_trunk_validation_res else None,
                "pass_validation": is_text_trunk_valid,
            },
            "seed_question": {
                "generated_question": generated_seed_question,
                "pass_validation": is_seed_question_valid,
                "reason": seed_question_validation_res.reason if seed_question_validation_res else None,
            },
            # "test_question": {},  # placeholder for evolved questions like multi-context, reasoning, etc.
            "suggested_answer": {
                "generated_suggested_answer": generated_suggested_answer,
                "pass_validation": is_suggested_answer_valid,
                "reason": suggested_answer_validation_res.reason if suggested_answer_validation_res else None,
            },
        },
    }
