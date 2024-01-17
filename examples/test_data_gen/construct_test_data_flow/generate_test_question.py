from typing import Union

from utils import is_valid_question, validate_distribution, get_question_type, generate_question

from promptflow import tool
from promptflow.connections import OpenAIConnection, AzureOpenAIConnection


@tool
def generate_test_question(
        connection: Union[OpenAIConnection, AzureOpenAIConnection],
        model: str,
        seed_question: str,
        reasoning_prompt: str,
        conditional_prompt: str,
        score_seed_question_prompt: str,
        simple_ratio: float = 0.5,
        reasoning_ratio: float = 0.25,
        conditional_ratio: float = 0.25
):
    """  
    Generates a test question based on the given prompts and distribution ratios.  
  
    Returns:  
        dict: The generated test question and its type.  
    """
    if seed_question is None or not is_valid_question(connection, model, score_seed_question_prompt):
        return None

    testset_distribution = validate_distribution(simple_ratio, reasoning_ratio, conditional_ratio)

    question_type = get_question_type(testset_distribution)
    question = generate_question(connection, model, question_type, seed_question, reasoning_prompt, conditional_prompt)

    return {"question": question, "question_type": question_type}
