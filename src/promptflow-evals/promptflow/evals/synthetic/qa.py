# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

"""Question-Answer Data Generator."""

import asyncio
import logging
import os
import time
from collections import defaultdict
from enum import Enum
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple, Union

from azure.core import CaseInsensitiveEnumMeta
from azure.core.tracing.decorator import distributed_trace
from packaging import version

from promptflow._sdk._telemetry import ActivityType, monitor_operation

logger = logging.getLogger(__name__)

try:
    import pkg_resources  # type: ignore[import]

    openai_version_str = pkg_resources.get_distribution("openai").version
    openai_version = pkg_resources.parse_version(openai_version_str)
    import openai

    if openai_version >= pkg_resources.parse_version("1.0.0"):
        _RETRY_ERRORS: Tuple = (openai.APIConnectionError, openai.APIError, openai.APIStatusError)
    else:
        _RETRY_ERRORS: Tuple = (
            openai.error.ServiceUnavailableError,  # pylint: disable=no-member
            openai.error.APIError,  # pylint: disable=no-member
            openai.error.RateLimitError,  # pylint: disable=no-member
            openai.error.APIConnectionError,  # pylint: disable=no-member
            openai.error.Timeout,  # pylint: disable=no-member
        )

except ImportError as e:
    logger.critical("In order to use qa, please install 'prompflow-evals")
    raise e

_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

_DEFAULT_AOAI_VERSION = "2023-07-01-preview"
_MAX_RETRIES = 7


def _completion_with_retries(*args, **kwargs):
    n = 1
    while True:
        try:
            if openai_version >= pkg_resources.parse_version("1.0.0"):
                if kwargs["api_type"].lower() == "azure":
                    from openai import AzureOpenAI

                    client = AzureOpenAI(
                        azure_endpoint=kwargs["api_base"],
                        api_key=kwargs["api_key"],
                        api_version=kwargs["api_version"],
                        # default_headers={USER_AGENT_HEADER_KEY: USER_AGENT},
                    )
                    response = client.chat.completions.create(
                        messages=kwargs["messages"],
                        model=kwargs["deployment_id"],
                        temperature=kwargs["temperature"],
                        max_tokens=kwargs["max_tokens"],
                    )
                else:
                    from openai import OpenAI

                    client = OpenAI(
                        api_key=kwargs["api_key"],
                        # default_headers={USER_AGENT_HEADER_KEY: USER_AGENT},
                    )
                    response = client.chat.completions.create(
                        messages=kwargs["messages"],
                        model=kwargs["model"],
                        temperature=kwargs["temperature"],
                        max_tokens=kwargs["max_tokens"],
                    )
                return response.choices[0].message.content, dict(response.usage)
            response = openai.ChatCompletion.create(*args, **kwargs)  # pylint: disable=no-member
            return response["choices"][0].message.content, response["usage"]
        except _RETRY_ERRORS as _re:  # pylint: disable=catching-non-exception # noqa: F841
            if n > _MAX_RETRIES:
                raise
            secs = 2**n
            # msg = f"Retrying after {secs}s. API call failed due to {_re.__class__.__name__}: {_re}"
            # logger.warning(msg)
            time.sleep(secs)
            n += 1
            continue


async def _completion_with_retries_async(*args, **kwargs):
    n = 1
    while True:
        try:
            if openai_version >= pkg_resources.parse_version("1.0.0"):
                if kwargs["api_type"].lower() == "azure":
                    from openai import AsyncAzureOpenAI

                    client = AsyncAzureOpenAI(
                        azure_endpoint=kwargs["api_base"],
                        api_key=kwargs["api_key"],
                        api_version=kwargs["api_version"],
                        # default_headers={USER_AGENT_HEADER_KEY: USER_AGENT},
                    )
                    response = await client.chat.completions.create(
                        messages=kwargs["messages"],
                        model=kwargs["deployment_id"],
                        temperature=kwargs["temperature"],
                        max_tokens=kwargs["max_tokens"],
                    )
                else:
                    from openai import AsyncOpenAI

                    client = AsyncOpenAI(
                        api_key=kwargs["api_key"],
                        # default_headers={USER_AGENT_HEADER_KEY: USER_AGENT},
                    )
                    response = await client.chat.completions.create(
                        messages=kwargs["messages"],
                        model=kwargs["model"],
                        temperature=kwargs["temperature"],
                        max_tokens=kwargs["max_tokens"],
                    )
                return response.choices[0].message.content, dict(response.usage)
            response = openai.ChatCompletion.create(*args, **kwargs)  # pylint: disable=no-member
            return response["choices"][0].message.content, response["usage"]
        except _RETRY_ERRORS as _re:  # pylint: disable=catching-non-exception # noqa: F841
            if n > _MAX_RETRIES:
                raise
            secs = 2**n
            # logger.warning("Retrying after %ss. API call failed due to %s: %s", secs, _re.__class__.__name__, _re)
            await asyncio.sleep(secs)
            n += 1
            continue


class OutputStructure(str, Enum, metaclass=CaseInsensitiveEnumMeta):
    """OutputStructure defines what structure the QAs should be written to file in."""

    PROMPTFLOW = "PROMPTFLOW"
    """Chat history will be in format used by promptflow"""
    CHAT_PROTOCOL = "CHAT_PROTOCOL"
    """QAs will be in OpenAI message format"""


class QAType(str, Enum, metaclass=CaseInsensitiveEnumMeta):
    """QAType defines different types of QAs that can be generated."""

    SHORT_ANSWER = "SHORT_ANSWER"
    """
        Short answer QAs have answers that are only a few words long.
        These words are generally relevant details from text like dates, names, statistics, etc.
    """
    LONG_ANSWER = "LONG_ANSWER"
    """
        Long answer QAs have answers that are one or more sentences long.
        ex. Questions where answer is a definition: What is a {topic_from_text}?
    """
    BOOLEAN = "BOOLEAN"
    """Boolean QAs have answers that are either True or False."""
    SUMMARY = "SUMMARY"
    """
        Summary QAs have questions that ask to write a summary for text's title in a limited number of words.
        It generates just one QA.
    """
    CONVERSATION = "CONVERSATION"
    """
        Conversation QAs have questions that might reference words or ideas from previous QAs.
        ex. If previous conversation was about some topicX from text, next question might reference it
        without using its name: How does *it* compare to topicY?
    """


class QADataGenerator:
    """Class for generating Question-Answer data from text."""

    _PARSING_ERR_UNEQUAL_QA = "Parsing error: Unequal question answer count"
    _PARSING_ERR_UNEQUAL_Q_AFTER_MOD = "Parsing error: Unequal question count after modification"
    _PARSING_ERR_FIRST_LINE = "Parsing error: First line must be a question"

    def __init__(self, model_config: Dict):
        """Initialize QADataGenerator using Azure OpenAI details."""

        api_key = "OPENAI_API_KEY"
        api_base = "OPENAI_API_BASE"
        if version.parse(openai.version.VERSION) >= version.parse("1.0.0"):
            api_key = "AZURE_OPENAI_KEY"
            api_base = "AZURE_OPENAI_ENDPOINT"
        self._chat_completion_params = dict(
            # AOAI connection params
            api_type=model_config["api_type"] if "api_type" in model_config else os.getenv("OPENAI_API_TYPE", "azure"),
            api_version=model_config["api_version"]
            if "api_version" in model_config
            else os.getenv("OPENAI_API_VERSION", _DEFAULT_AOAI_VERSION),
            api_base=model_config["api_base"] if "api_base" in model_config else os.getenv(api_base),
            api_key=model_config["api_key"] if "api_key" in model_config else os.getenv(api_key),
            # AOAI model params
            deployment_id=model_config["deployment"],
            model=model_config["model"],
            max_tokens=model_config.get("max_tokens", 2000),
            temperature=0.0,  # don't need creativity
        )

        # activity_logger.update_info()

    def _validate(self, qa_type: QAType, num_questions: Optional[int]):
        if qa_type == QAType.SUMMARY and num_questions is not None:
            raise ValueError("num_questions unsupported for Summary QAType")
        if qa_type != QAType.SUMMARY and num_questions <= 0:  # type: ignore[operator]
            raise ValueError("num_questions must be an integer greater than zero")

    def _get_messages_for_qa_type(self, qa_type: QAType, text: str, num_questions: int) -> List:
        # logger.debug("Getting prompt messages for %s QA type", qa_type)
        template_filename = {
            QAType.SHORT_ANSWER: "prompt_qa_short_answer.txt",
            QAType.LONG_ANSWER: "prompt_qa_long_answer.txt",
            QAType.BOOLEAN: "prompt_qa_boolean.txt",
            QAType.SUMMARY: "prompt_qa_summary.txt",
            QAType.CONVERSATION: "prompt_qa_conversation.txt",
        }
        filename = template_filename[qa_type]
        messages = self._get_messages_from_file(filename)
        input_variables: Dict[str, Any] = {"text": text}
        if qa_type == QAType.SUMMARY:
            input_variables["num_words"] = 100
        else:
            input_variables["num_questions"] = num_questions
        messages[-1]["content"] = messages[-1]["content"].format(**input_variables)
        return messages

    def _get_messages_for_modify_conversation(self, questions: List[str]) -> List:
        messages = self._get_messages_from_file("prompt_qa_conversation_modify.txt")
        questions_str = "\n".join([f"[Q]: {q}" for q in questions])
        messages[-1]["content"] = messages[-1]["content"].format(questions=questions_str)
        return messages

    def _get_messages_from_file(self, filename: str) -> List:
        template = self._get_template(filename)
        content_list = [content.strip() for content in template.split("<|separator|>")]
        messages = [
            {"role": "system", "content": content_list[0]},  # system instructions
            {"role": "user", "content": content_list[1]},  # few-shot input
            {"role": "assistant", "content": content_list[2]},  # few-shot output
            {"role": "user", "content": content_list[3]},  # input template
        ]
        return messages

    @lru_cache
    def _get_template(self, filename) -> str:
        # logger.debug("Getting prompt template from %s file", filename)
        filepath = os.path.join(_TEMPLATES_DIR, filename)
        with open(filepath, encoding="utf-8") as f:
            template = f.read()
        return template

    def _parse_qa_from_response(self, response_text: str) -> Tuple[List[str], List[str]]:
        q_prefix, a_prefix = "[Q]: ", "[A]: "
        last_updated = None
        questions, answers = [], []
        for line in response_text.split("\n"):
            if line.startswith(q_prefix):
                questions.append(line[len(q_prefix) :])
                last_updated = "Q"
            elif line.startswith(a_prefix):
                answers.append(line[len(a_prefix) :])
                last_updated = "A"
            else:  # Q or A spread across multiple lines
                assert last_updated is not None, self._PARSING_ERR_FIRST_LINE
                if last_updated == "Q":
                    questions[-1] += "\n" + line
                else:
                    answers[-1] += "\n" + line
        return questions, answers

    def _merge_token_usage(self, token_usage: Dict, token_usage2: Dict) -> Dict:
        return {name: count + token_usage[name] for name, count in token_usage2.items()}

    def _modify_conversation_questions(self, questions) -> Tuple[List[str], Dict]:
        content, usage = _completion_with_retries(
            messages=self._get_messages_for_modify_conversation(questions),
            **self._chat_completion_params,
        )

        modified_questions, _ = self._parse_qa_from_response(content)
        # Keep proper nouns in first question of conversation
        modified_questions[0] = questions[0]
        assert len(modified_questions) == len(questions), self._PARSING_ERR_UNEQUAL_Q_AFTER_MOD
        return modified_questions, usage

    @distributed_trace
    @monitor_operation(activity_name="pf.evals.QADataGenerator.Export", activity_type=ActivityType.INTERNALCALL)
    def export_to_file(
        self,
        output_path: str,
        qa_type: QAType,
        results: Union[List, List[List]],
        output_format: OutputStructure = OutputStructure.PROMPTFLOW,
        field_mapping: Optional[Dict[str, str]] = None,
    ):
        """
        Writes results from QA gen to a jsonl file for Promptflow batch run results is either a list of questions
        and answers or list of list of questions and answers grouped by their chunk e.g. [("How are you?",
        "I am good.")] or [ [("How are you?", "I am good.")], [("What can I do?", "Tell me a joke.")].

        :param output_path: The path to the output file.
        :type output_path: str
        :param qa_type: The type of QA data.
        :type qa_type: QAType
        :param results: The results of the QA generation.
        :type results: Union[List, List[List]]
        :param output_format: The output structure format.
        :type output_format: OutputStructure, optional
        :param field_mapping: The field mapping for the output structure.
        :type field_mapping: Optional[Dict[str, str]], optional
        """
        data_dict = defaultdict(list)

        if field_mapping is None:
            field_mapping = {"chat_history_key": "chat_history", "question_key": "question"}

        if not isinstance(results[0], List):
            results = [results]

        if output_format == OutputStructure.PROMPTFLOW:

            if qa_type == QAType.CONVERSATION and not (
                "chat_history_key" in field_mapping and "question_key" in field_mapping
            ):
                keys = "chat_history_key, question_key"
                raise Exception(
                    "Field mapping for Promptflow output with Conversation must contain following keys: " + keys
                )
            # Only the question key is required in non-conversation cases,
            # we can default to chat_history as chat_history_key
            if "question_key" not in field_mapping:
                raise Exception(
                    f"Field mapping for Promptflow output with {qa_type} must contain following keys: question_key"
                )

            question_key = field_mapping["question_key"]
            # Set this here for parity with eval flows
            answer_key = "ground_truth"
            chat_history_key = field_mapping.get("chat_history_key", "chat_history")
            for qs_and_as in results:
                chat_history: List = []
                for question, answer in qs_and_as:
                    data_dict[chat_history_key].append(list(chat_history))
                    if qa_type == QAType.CONVERSATION:
                        # Chat History columns:
                        data_dict[question_key].append(question)
                        chat_history.append({"inputs": {question_key: question}, "outputs": {answer_key: answer}})
                    else:
                        # QnA columns:
                        data_dict[question_key].append(question)

                    data_dict[answer_key].append(answer)  # Consider generated answer as the ground truth
        else:
            for qs_and_as in results:
                chat_history = []
                for question, answer in qs_and_as:
                    if qa_type == QAType.CONVERSATION:
                        chat_history.append({"role": "user", "content": question})
                        chat_history.append({"role": "assistant", "content": answer})
                        data_dict["messages"].append(list(chat_history))
                    else:
                        messages = []
                        messages.append({"role": "user", "content": question})
                        messages.append({"role": "assistant", "content": answer})
                        data_dict["messages"].append(list(messages))
        # export to jsonl file
        try:
            import pandas as pd
        except ImportError as ie:
            logger.critical("In order to write qa data to file, please install pandas")
            raise ie

        data_df = pd.DataFrame(data_dict, columns=list(data_dict.keys()))
        data_df.to_json(output_path, lines=True, orient="records")

    @distributed_trace
    @monitor_operation(activity_name="pf.evals.QADataGenerator.Generate", activity_type=ActivityType.INTERNALCALL)
    def generate(self, text: str, qa_type: QAType, num_questions: Optional[int] = None) -> Dict:
        self._validate(qa_type, num_questions)
        validated_num_questions: int = num_questions  # type: ignore[assignment]
        content, token_usage = _completion_with_retries(
            messages=self._get_messages_for_qa_type(qa_type, text, validated_num_questions),
            **self._chat_completion_params,
        )
        questions, answers = self._parse_qa_from_response(content)
        assert len(questions) == len(answers), self._PARSING_ERR_UNEQUAL_QA
        if qa_type == QAType.CONVERSATION:
            questions, token_usage2 = self._modify_conversation_questions(questions)
            token_usage = self._merge_token_usage(token_usage, token_usage2)
        return {
            "question_answers": list(zip(questions, answers)),
            "token_usage": token_usage,
        }

    async def _modify_conversation_questions_async(self, questions) -> Tuple[List[str], Dict]:
        content, usage = await _completion_with_retries_async(
            messages=self._get_messages_for_modify_conversation(questions),
            **self._chat_completion_params,
        )

        modified_questions, _ = self._parse_qa_from_response(content)
        # Keep proper nouns in first question of conversation
        modified_questions[0] = questions[0]
        assert len(modified_questions) == len(questions), self._PARSING_ERR_UNEQUAL_Q_AFTER_MOD
        return modified_questions, usage

    @distributed_trace
    @monitor_operation(activity_name="pf.evals.QADataGenerator.GenerateAsync", activity_type=ActivityType.INTERNALCALL)
    async def generate_async(self, text: str, qa_type: QAType, num_questions: Optional[int] = None) -> Dict:
        self._validate(qa_type, num_questions)
        validated_num_questions: int = num_questions  # type: ignore[assignment]
        content, token_usage = await _completion_with_retries_async(
            messages=self._get_messages_for_qa_type(qa_type, text, validated_num_questions),
            **self._chat_completion_params,
        )
        questions, answers = self._parse_qa_from_response(content)
        assert len(questions) == len(answers), self._PARSING_ERR_UNEQUAL_QA
        if qa_type == QAType.CONVERSATION:
            questions, token_usage2 = await self._modify_conversation_questions_async(questions)
            token_usage = self._merge_token_usage(token_usage, token_usage2)
        return {
            "question_answers": list(zip(questions, answers)),
            "token_usage": token_usage,
        }
