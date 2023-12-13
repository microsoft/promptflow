from promptflow import tool
from promptflow.contracts.multimedia import Image


@tool
def passthrough(image: Image, question: list, chat_history: list):
    return question
