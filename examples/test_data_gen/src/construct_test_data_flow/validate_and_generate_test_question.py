from typing import Union

from utils import QuestionType, is_valid_question

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection


@tool
def validate_and_generate_test_question(
    connection: Union[OpenAIConnection, AzureOpenAIConnection],
    model: str,
    seed_question: str,
    # reasoning_prompt: str,
    # conditional_prompt: str,
    validate_seed_question_prompt: str,
    # simple_ratio: float = 0.5,
    # reasoning_ratio: float = 0.25,
    # conditional_ratio: float = 0.25
):
    """
    1. Validates the given seed question.
    2. Generates a test question based on the given prompts and distribution ratios.

    Returns:
        dict: The generated test question and its type.
    """
    # text trunk is not valid, seed question not generated.
    if not seed_question:
        return {"question": "", "question_type": ""}

    is_valid_seed_question = is_valid_question(connection, model, validate_seed_question_prompt, seed_question)
    if not is_valid_seed_question:
        print(f"Invalid seed question: {seed_question}")
        return {"question": "", "question_type": ""}

    # TODO: add multi_context prompt (p3)
    # TODO: add reasoning prompt and conditional prompt (p4)
    # testset_distribution = validate_distribution(simple_ratio, reasoning_ratio, conditional_ratio)

    # question_type = get_question_type(testset_distribution)
    # question = generate_question(connection, model, question_type, seed_question)

    return {"question": seed_question, "question_type": QuestionType.SIMPLE}
