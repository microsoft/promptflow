import json
import re

import numpy as np
import numpy.testing as npt
import openai
from numpy.random import default_rng

from promptflow.connections import AzureOpenAIConnection, OpenAIConnection


class QuestionType:
    SIMPLE = "simple"
    REASONING = "reasoning"
    CONDITIONAL = "conditional"
    # MULTI_CONTEXT = "multi_context"


def parse_chat(prompt):
    messages = [
        {"role": role, "content": content.strip()}
        for role, content in re.findall(r"(system|user):(.*?)$", prompt, re.DOTALL)
    ]
    return messages


def llm_call(connection, model, prompt):
    client = get_client_by_connection_type(connection)
    messages = parse_chat(prompt)
    return client.chat.completions.create(model=model, messages=messages).choices[0].message.content


def get_client_by_connection_type(connection):
    if isinstance(connection, AzureOpenAIConnection):
        return openai.AzureOpenAI(
            api_key=connection.api_key, api_version=connection.api_version, azure_endpoint=connection.api_base
        )
    elif isinstance(connection, OpenAIConnection):
        return openai.OpenAI(
            api_key=connection.api_key, base_url=connection.base_url, organization=connection.organization
        )


def get_question_type(testset_distribution) -> str:
    """
    Decides question evolution type based on probability
    """
    rng = default_rng()
    prob = rng.uniform(0, 1)
    return next((key for key in testset_distribution.keys() if prob <= testset_distribution[key]), QuestionType.SIMPLE)


def is_valid_question(connection, model, prompt, question: str = None):
    answer = llm_call(connection, model, prompt)
    # Load the JSON string into a Python dictionary
    data = json.loads(answer)

    # Extract the verdict and reason
    verdict = data["verdict"].lower()
    reason = data["reason"]
    print(f"Is valid question: {verdict}\nReason: {reason}")
    if verdict == "yes":
        return True
    elif verdict == "no":
        return False
    else:
        print(f"Unexpected llm response to validate queston: {question}")

    return False


def is_valid_text_trunk(answer: str, context: str = None):
    data = json.loads(answer)

    # Extract the verdict and reason
    verdict = data["verdict"].lower()
    reason = data["reason"]
    print(f"Is valid text trunk: {verdict}\nReason: {reason}")
    if verdict == "yes":
        return True
    elif verdict == "no":
        return False
    else:
        print(f"Unexpected llm response to validate text trunk: {context}")

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
