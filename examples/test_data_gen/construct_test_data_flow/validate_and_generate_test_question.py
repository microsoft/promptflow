from typing import Union

from utils import generate_question, get_question_type, is_valid_question, validate_distribution

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection


@tool
def validate_and_generate_test_question(
        connection: Union[OpenAIConnection, AzureOpenAIConnection],
        model: str,
        seed_question: str,
        reasoning_prompt: str,
        conditional_prompt: str,
        validate_seed_question_prompt: str,
        simple_ratio: float = 0.5,
        reasoning_ratio: float = 0.25,
        conditional_ratio: float = 0.25
):
    """
    1. Validates the given seed question.  
    2. Generates a test question based on the given prompts and distribution ratios.  
  
    Returns:  
        dict: The generated test question and its type.  
    """
    if not seed_question or not is_valid_question(connection, model, validate_seed_question_prompt):
        return {"question": "", "question_type": ""}

    testset_distribution = validate_distribution(simple_ratio, reasoning_ratio, conditional_ratio)

    question_type = get_question_type(testset_distribution)
    question = generate_question(connection, model, question_type, seed_question, reasoning_prompt, conditional_prompt)

    return {"question": question, "question_type": question_type}
