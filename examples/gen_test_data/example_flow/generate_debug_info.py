from utils import ValidateObj, ValidationResult

from promptflow.core import tool


# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need
@tool
def my_python_tool(
    text_chunk: str,
    text_chunk_validation_res: ValidationResult = None,
    validate_question_output: dict = None,
    validate_suggested_answer_output: dict = None,
) -> dict:
    question_validation_res = validate_question_output["validation_res"]

    generated_suggested_answer = validate_suggested_answer_output["suggested_answer"]
    suggested_answer_validation_res = validate_suggested_answer_output["validation_res"]

    is_generation_success = generated_suggested_answer != ""
    is_text_chunk_valid = text_chunk_validation_res["pass_validation"] if text_chunk_validation_res else None
    is_seed_question_valid = question_validation_res["pass_validation"] if question_validation_res else None
    is_suggested_answer_valid = (
        suggested_answer_validation_res["pass_validation"] if suggested_answer_validation_res else None
    )

    failed_step = ""
    if not is_generation_success:
        if is_text_chunk_valid is False:
            failed_step = ValidateObj.TEXT_CHUNK
        elif is_seed_question_valid is False:
            failed_step = ValidateObj.QUESTION
        elif is_suggested_answer_valid is False:
            failed_step = ValidateObj.SUGGESTED_ANSWER

    return {
        # TODO: support more question types like multi-context etc.
        # "question_type": question_type,
        "text_chunk": text_chunk,
        "validation_summary": {"success": is_generation_success, "failed_step": failed_step},
        "validation_details": {
            ValidateObj.TEXT_CHUNK: text_chunk_validation_res,
            ValidateObj.QUESTION: question_validation_res,
            ValidateObj.SUGGESTED_ANSWER: suggested_answer_validation_res,
        },
    }
