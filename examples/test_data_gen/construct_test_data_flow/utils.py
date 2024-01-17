import json
import re

import numpy as np
import numpy.testing as npt
import openai
from numpy.random import default_rng

from promptflow.connections import OpenAIConnection, AzureOpenAIConnection


def parse_chat(prompt):
    messages = [{'role': role, 'content': content.strip()} for role, content in
                re.findall(r'(system|user):(.*?)$', prompt, re.DOTALL)]
    return messages


def llm_call(connection, model, prompt):
    client = get_client_by_connection_type(connection)
    messages = parse_chat(prompt)
    return client.chat.completions.create(model=model, messages=messages).choices[0].message.content


def get_client_by_connection_type(connection):
    if isinstance(connection, AzureOpenAIConnection):
        return openai.AzureOpenAI(api_key=connection.api_key, api_version=connection.api_version,
                                  azure_endpoint=connection.api_base)
    elif isinstance(connection, OpenAIConnection):
        return openai.OpenAI(api_key=connection.api_key, base_url=connection.base_url,
                             organization=connection.organization)


def get_question_type(testset_distribution) -> str:
    """
    Decides question evolution type based on probability
    """
    rng = default_rng()
    prob = rng.uniform(0, 1)
    return next(
        (
            key
            for key in testset_distribution.keys()
            if prob <= testset_distribution[key]
        ),
        "simple")


def is_valid_question(connection, model, prompt):
    is_valid = json.loads(llm_call(connection, model, prompt))["verdict"] != "No"
    if not is_valid:
        print("Invalid question.")
    return is_valid


def validate_distribution(simple_ratio, reasoning_ratio, conditional_ratio):
    testset_distribution = {
        "simple": simple_ratio,
        "reasoning": reasoning_ratio,
        "conditional": conditional_ratio,
    }
    npt.assert_almost_equal(1, sum(testset_distribution.values()), err_msg="Sum of distribution should be 1")
    testset_distribution = dict(zip(testset_distribution.keys(), np.cumsum(list(testset_distribution.values()))))
    return testset_distribution


def generate_question(connection, model, question_type, seed_question, reasoning_prompt, conditional_prompt):
    if question_type == "simple":
        return seed_question
    elif question_type == "reasoning":
        return llm_call(connection, model, reasoning_prompt)
    elif question_type == "conditional":
        return llm_call(connection, model, conditional_prompt)
    else:
        raise Exception("Invalid question type.")
