import json
import re
from collections import namedtuple

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
    SUGGESTED_ANSWER = "suggested_answer"


class ResponseFormat:
    TEXT = "text"
    JSON = "json_object"


class ErrorMsg:
    INVALID_JSON_FORMAT = "llm failed to return the verdict and reason in correct json format. Response: {0}"
    INVALID_TEXT_TRUNK = "Skipping generating seed question due to invalid text chunk."
    INVALID_QUESTION = "Invalid seed question: {0}"
    INVALID_ANSWER = "Invalid answer: {0}"


ValidationResult = namedtuple("ValidationResult", ["pass_validation", "reason_if_failed"])


def llm_call(
        connection,
        model_or_deployment_name,
        prompt,
        response_format=ResponseFormat.TEXT,
        temperature=1.0,
        max_tokens=16
):
    response_format = "json_object" if response_format.lower() == "json" else response_format
    prompt = f"{{% raw %}}{prompt}{{% endraw %}}"
    if isinstance(connection, AzureOpenAIConnection):
        return aoai_chat(
            connection=connection,
            prompt=prompt,
            deployment_name=model_or_deployment_name,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": response_format}
        )
    elif isinstance(connection, OpenAIConnection):
        return openai_chat(
            connection=connection,
            prompt=prompt,
            model=model_or_deployment_name,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": response_format})


def get_question_type(testset_distribution) -> str:
    """
    Decides question evolution type based on probability
    """
    rng = default_rng()
    prob = rng.uniform(0, 1)
    return next((key for key in testset_distribution.keys() if prob <= testset_distribution[key]), QuestionType.SIMPLE)


def get_suggested_answer_validation_res(connection, model_or_deployment_name, prompt, suggested_answer: str,
                                        temperature: float,
                                        max_tokens: int):
    rsp = llm_call(connection, model_or_deployment_name, prompt, temperature=temperature, max_tokens=max_tokens)
    return retrieve_verdict_and_print_reason(
        rsp=rsp, validate_obj_name=ValidateObj.SUGGESTED_ANSWER, validate_obj=suggested_answer
    )


def get_question_validation_res(connection, model_or_deployment_name, prompt, question: str,
                                response_format: ResponseFormat, temperature: float,
                                max_tokens: int):
    rsp = llm_call(connection, model_or_deployment_name, prompt, response_format, temperature, max_tokens)
    return retrieve_verdict_and_print_reason(rsp=rsp, validate_obj_name=ValidateObj.QUESTION, validate_obj=question)


def get_text_trunk_validation_res(connection, model_or_deployment_name, prompt, context: str,
                                  response_format: ResponseFormat, temperature: float,
                                  max_tokens: int):
    rsp = llm_call(connection, model_or_deployment_name, prompt, response_format, temperature, max_tokens)
    return retrieve_verdict_and_print_reason(rsp=rsp, validate_obj_name=ValidateObj.TEXT_TRUNK, validate_obj=context)


def retrieve_verdict_and_print_reason(rsp: str, validate_obj_name: str, validate_obj: str) -> ValidationResult:
    try:
        # It is possible that even the response format is required as json, the response still contains ```json\n
        rsp = re.sub(r"```json\n?|```", "", rsp)
        data = json.loads(rsp)
    except json.decoder.JSONDecodeError:
        print(ErrorMsg.INVALID_JSON_FORMAT.format(rsp))
        data = None

    if data and isinstance(data, dict) and "verdict" in data and "reason" in data:
        # Extract the verdict and reason
        verdict = data["verdict"].lower()
        reason = data["reason"]
        print(f"Is valid {validate_obj_name}: {verdict}\nReason: {reason}")
        if verdict == "yes":
            return ValidationResult(True, "")
        elif verdict == "no":
            return ValidationResult(False, reason)
        else:
            print(f"Unexpected llm response to validate {validate_obj_name}: {validate_obj}")

    return ValidationResult(False, ErrorMsg.INVALID_JSON_FORMAT.format(rsp))


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
        connection, model_or_deployment_name, question_type, seed_question, reasoning_prompt: str = None,
        conditional_prompt: str = None, temperature: float = None,
        max_tokens: int = None
):
    if question_type == QuestionType.SIMPLE:
        return seed_question
    elif question_type == QuestionType.REASONING:
        return llm_call(connection, model_or_deployment_name, reasoning_prompt, temperature=temperature,
                        max_tokens=max_tokens)
    elif question_type == QuestionType.CONDITIONAL:
        return llm_call(connection, model_or_deployment_name, conditional_prompt, temperature=temperature,
                        max_tokens=max_tokens)
    else:
        raise Exception("Invalid question type.")
