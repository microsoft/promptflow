import time
from typing import List
import re
import tiktoken
import logging
import sys
import json

FORMATTER = logging.Formatter(
    fmt="[%(asctime)s] %(name)-8s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S %z",
)


def get_logger(name: str, level=logging.INFO) -> logging.Logger:
    logger = logging.Logger(name)
    # log to sys.stdout for backward compatibility.
    # TODO: May need to be removed in the future, after local/blob file stream are fully supported.
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(FORMATTER)
    logger.addHandler(stdout_handler)
    logger.setLevel(level)
    return logger


def parse_reply(text: str):
    try:
        parsed = json.loads(text, strict=False)
    except json.JSONDecodeError:
        preprocessed_text = preprocess_json_input(text)
        try:
            parsed = json.loads(preprocessed_text, strict=False)
        except Exception:
            return {"Error": f"Could not parse invalid json: {text}"}
    except TypeError:
        return {"Error": f"the JSON object must be str, bytes or bytearray not {type(text)}"}
    return parsed


def count_message_tokens(
    messages: List, model: str = "gpt-3.5-turbo-0301"
) -> int:
    """
    Returns the number of tokens used by a list of messages.

    Args:
        messages (list): A list of messages, each of which is a dictionary
            containing the role and content of the message.
        model (str): The name of the model to use for tokenization.
            Defaults to "gpt-3.5-turbo-0301".

    Returns:
        int: The number of tokens used by the list of messages.
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    if model == "gpt-3.5-turbo":
        # !Note: gpt-3.5-turbo may change over time.
        # Returning num tokens assuming gpt-3.5-turbo-0301.")
        return count_message_tokens(messages, model="gpt-3.5-turbo-0301")
    elif model == "gpt-4":
        # !Note: gpt-4 may change over time. Returning num tokens assuming gpt-4-0314.")
        return count_message_tokens(messages, model="gpt-4-0314")
    elif model == "gpt-3.5-turbo-0301":
        tokens_per_message = (
            4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        )
        tokens_per_name = -1  # if there's a name, the role is omitted
    elif model == "gpt-4-0314":
        tokens_per_message = 3
        tokens_per_name = 1
    else:
        raise NotImplementedError(
            f"num_tokens_from_messages() is not implemented for model {model}.\n"
            " See https://github.com/openai/openai-python/blob/main/chatml.md for"
            " information on how messages are converted to tokens."
        )
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens


def count_string_tokens(string: str, model_name="gpt-3.5-turbo") -> int:
    """
    Returns the number of tokens in a text string.

    Args:
        string (str): The text string.
        model_name (str): The name of the encoding to use. (e.g., "gpt-3.5-turbo")

    Returns:
        int: The number of tokens in the text string.
    """
    encoding = tiktoken.encoding_for_model(model_name)
    return len(encoding.encode(string))


def create_chat_message(role, content, name=None):
    """
    Create a chat message with the given role and content.

    Args:
    role (str): The role of the message sender, e.g., "system", "user", or "assistant".
    content (str): The content of the message.

    Returns:
    dict: A dictionary containing the role and content of the message.
    """
    if name is None:
        return {"role": role, "content": content}
    else:
        return {"role": role, "name": name, "content": content}


def generate_context(prompt, full_message_history, user_prompt, model="gpt-3.5-turbo"):
    current_context = [
        create_chat_message("system", prompt),
        create_chat_message(
            "system", f"The current time and date is {time.strftime('%c')}"
        ),
        create_chat_message("user", user_prompt),
    ]

    # Add messages from the full message history until we reach the token limit
    next_message_to_add_index = len(full_message_history) - 1
    insertion_index = len(current_context)
    # Count the currently used tokens
    current_tokens_used = count_message_tokens(current_context, model)
    return (
        next_message_to_add_index,
        current_tokens_used,
        insertion_index,
        current_context,
    )


def preprocess_json_input(input_str: str) -> str:
    # Replace single backslashes with double backslashes, while leaving already escaped ones intact
    corrected_str = re.sub(r'(?<!\\)\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r"\\\\", input_str)
    return corrected_str


def construct_prompt(current_context):
    update_current_context = []
    for item in current_context:
        role = item.get("role", None)
        content = item.get("content", None)
        name = item.get("name", None)

        if name is not None:
            update_current_context.append(":\n".join([role, "name", name]) + "\n" + ":\n".join(["content", content]))
        else:
            update_current_context.append(":\n".join([role, content]))
    update_current_context = "\n".join(update_current_context)
    return update_current_context
