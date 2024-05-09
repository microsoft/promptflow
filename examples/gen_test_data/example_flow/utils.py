import json
import re
from collections import namedtuple

from numpy.random import default_rng

from promptflow.connections import AzureOpenAIConnection, OpenAIConnection
from promptflow.tools.aoai import chat as aoai_chat
from promptflow.tools.openai import chat as openai_chat


class QuestionType:
    SIMPLE = "simple"
    # MULTI_CONTEXT = "multi_context"


class ValidateObj:
    QUESTION = "validate_question"
    TEXT_CHUNK = "validate_text_chunk"
    SUGGESTED_ANSWER = "validate_suggested_answer"


class ResponseFormat:
    TEXT = "text"
    JSON = "json_object"


class ErrorMsg:
    INVALID_JSON_FORMAT = "Invalid json format. Response: {0}"
    INVALID_TEXT_CHUNK = "Skipping generating seed question due to invalid text chunk: {0}"
    INVALID_QUESTION = "Invalid seed question: {0}"
    INVALID_ANSWER = "Invalid answer: {0}"


ValidationResult = namedtuple("ValidationResult", ["pass_validation", "reason"])
ScoreResult = namedtuple("ScoreResult", ["score", "reason", "pass_validation"])


def llm_call(
    connection, model, deployment_name, prompt, response_format=ResponseFormat.TEXT, temperature=1.0, max_tokens=None
):
    response_format = "json_object" if response_format.lower() == "json" else response_format
    # avoid unnecessary jinja2 template re-rendering and potential error.
    prompt = f"{{% raw %}}{prompt}{{% endraw %}}"
    if isinstance(connection, AzureOpenAIConnection):
        return aoai_chat(
            connection=connection,
            prompt=prompt,
            deployment_name=deployment_name,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": response_format},
        )
    elif isinstance(connection, OpenAIConnection):
        return openai_chat(
            connection=connection,
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": response_format},
        )


def get_question_type(testset_distribution) -> str:
    """
    Decides question evolution type based on probability
    """
    rng = default_rng()
    prob = rng.uniform(0, 1)
    return next((key for key in testset_distribution.keys() if prob <= testset_distribution[key]), QuestionType.SIMPLE)


def get_suggested_answer_validation_res(
    connection,
    model,
    deployment_name,
    prompt,
    suggested_answer: str,
    temperature: float,
    max_tokens: int = None,
    response_format: ResponseFormat = ResponseFormat.TEXT,
):
    rsp = llm_call(
        connection,
        model,
        deployment_name,
        prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=response_format,
    )
    return retrieve_verdict_and_print_reason(
        rsp=rsp, validate_obj_name=ValidateObj.SUGGESTED_ANSWER, validate_obj=suggested_answer
    )


def get_question_validation_res(
    connection,
    model,
    deployment_name,
    prompt,
    question: str,
    response_format: ResponseFormat,
    temperature: float,
    max_tokens: int = None,
):
    rsp = llm_call(connection, model, deployment_name, prompt, response_format, temperature, max_tokens)
    return retrieve_verdict_and_print_reason(rsp=rsp, validate_obj_name=ValidateObj.QUESTION, validate_obj=question)


def get_text_chunk_score(
    connection,
    model,
    deployment_name,
    prompt,
    response_format: ResponseFormat,
    score_threshold: float,
    temperature: float,
    max_tokens: int = None,
):
    rsp = llm_call(connection, model, deployment_name, prompt, response_format, temperature, max_tokens)
    data = _load_json_rsp(rsp)
    score_float = 0
    reason = ""

    if data and isinstance(data, dict) and "score" in data and "reason" in data:
        # Extract the verdict and reason
        score = data["score"].lower()
        reason = data["reason"]
        print(f"Score {ValidateObj.TEXT_CHUNK}: {score}\nReason: {reason}")
        try:
            score_float = float(score)
        except ValueError:
            reason = ErrorMsg.INVALID_JSON_FORMAT.format(rsp)
    else:
        reason = ErrorMsg.INVALID_JSON_FORMAT.format(rsp)
    pass_validation = score_float >= score_threshold

    return ScoreResult(score_float, reason, pass_validation)


def retrieve_verdict_and_print_reason(rsp: str, validate_obj_name: str, validate_obj: str) -> ValidationResult:
    data = _load_json_rsp(rsp)

    if data and isinstance(data, dict) and "verdict" in data and "reason" in data:
        # Extract the verdict and reason
        verdict = data["verdict"].lower()
        reason = data["reason"]
        print(f"Is valid {validate_obj_name}: {verdict}\nReason: {reason}")
        if verdict == "yes":
            return ValidationResult(True, reason)
        elif verdict == "no":
            return ValidationResult(False, reason)
        else:
            print(f"Unexpected llm response to validate {validate_obj_name}: {validate_obj}")

    return ValidationResult(False, ErrorMsg.INVALID_JSON_FORMAT.format(rsp))


def _load_json_rsp(rsp: str):
    try:
        # It is possible that even the response format is required as json, the response still contains ```json\n
        rsp = re.sub(r"```json\n?|```", "", rsp)
        data = json.loads(rsp)
    except json.decoder.JSONDecodeError:
        print(ErrorMsg.INVALID_JSON_FORMAT.format(rsp))
        data = None

    return data
