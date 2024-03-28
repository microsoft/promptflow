import os

from promptflow.core import tool
from promptflow.connections import CustomConnection

from intent import extract_intent


@tool
def extract_intent_tool(chat_prompt, connection: CustomConnection) -> str:

    # set environment variables
    for key, value in dict(connection).items():
        os.environ[key] = value

    # call the entry function
    return extract_intent(
        chat_prompt=chat_prompt,
    )
