import json

import numpy as np
import numpy.testing as npt
from numpy.random import default_rng
from promptflow.tools.aoai import chat as aoai_chat
from promptflow.tools.openai import chat as openai_chat

from promptflow.connections import AzureOpenAIConnection, OpenAIConnection


class QuestionType:
    SIMPLE = "simple"
    REASONING = "reasoning"
    CONDITIONAL = "conditional"
    # MULTI_CONTEXT = "multi_context"


class ValidateObj:
    QUESTION = "question"
    TEXT_TRUNK = "text_trunk"
    GROUNDTRUTH = "ground_truth"


def llm_call(connection, model, prompt, response_format="text"):
    response_format = "json_object" if response_format.lower() == "json" else response_format
    if isinstance(connection, AzureOpenAIConnection):
        return aoai_chat(
            connection=connection,
            prompt=prompt,
            deployment_name=model,
            response_format={"type": response_format}
        )
    elif isinstance(connection, OpenAIConnection):
        return openai_chat(
            connection=connection,
            prompt=prompt,
            model=model,
            response_format={"type": response_format}
        )


def get_question_type(testset_distribution) -> str:
    """
    Decides question evolution type based on probability
    """
    rng = default_rng()
    prob = rng.uniform(0, 1)
    return next((key for key in testset_distribution.keys() if prob <= testset_distribution[key]), QuestionType.SIMPLE)


def is_valid_ground_truth(connection, model, prompt, ground_truth: str):
    answer = llm_call(connection, model, prompt)
    return retrieve_verdict_and_print_reason(
        answer=answer, validate_obj_name=ValidateObj.GROUNDTRUTH, validate_obj=ground_truth
    )


def is_valid_question(connection, model, prompt, question: str):
    answer = llm_call(connection, model, prompt, "json_object")
    return retrieve_verdict_and_print_reason(
        answer=answer, validate_obj_name=ValidateObj.QUESTION, validate_obj=question
    )


def is_valid_text_trunk(connection, model, prompt, context: str):
    answer = llm_call(connection, model, prompt, "json_object")
    return retrieve_verdict_and_print_reason(
        answer=answer, validate_obj_name=ValidateObj.TEXT_TRUNK, validate_obj=context
    )


def retrieve_verdict_and_print_reason(answer: str, validate_obj_name: str, validate_obj: str) -> bool:
    try:
        data = json.loads(answer)
    except json.decoder.JSONDecodeError:
        print("llm failed to return the verdict and reason in correct json format.")
        data = None

    if data and isinstance(data, dict) and "verdict" in data and "reason" in data:
        # Extract the verdict and reason
        verdict = data["verdict"].lower()
        reason = data["reason"]
        print(f"Is valid {validate_obj_name}: {verdict}\nReason: {reason}")
        if verdict == "yes":
            return True
        elif verdict == "no":
            return False
        else:
            print(f"Unexpected llm response to validate {validate_obj_name}: {validate_obj}")

    return False


def validate_distribution(simple_ratio, reasoning_ratio, conditional_ratio):
    testset_distribution = {
        QuestionType.SIMPLE: simple_ratio,
        QuestionType.REASONING: reasoning_ratio,
        QuestionType.CONDITIONAL: conditional_ratio,
    }
    npt.assert_almost_equal(1, sum(testset_distribution.values()), err_msg="Sum of distribution should be 1")
    testset_distribution = dict(zip(testset_distribution.keys(), np.cumsum(list(testset_distribution.values()))))
    return testset_distribution


def generate_question(
        connection, model, question_type, seed_question, reasoning_prompt: str = None, conditional_prompt: str = None
):
    if question_type == QuestionType.SIMPLE:
        return seed_question
    elif question_type == QuestionType.REASONING:
        return llm_call(connection, model, reasoning_prompt)
    elif question_type == QuestionType.CONDITIONAL:
        return llm_call(connection, model, conditional_prompt)
    else:
        raise Exception("Invalid question type.")
