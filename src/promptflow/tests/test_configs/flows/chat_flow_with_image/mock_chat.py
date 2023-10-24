from promptflow import tool
from promptflow.contracts.multimedia import Image


@tool
def mock_chat(chat_history: list, question: list):
    res = []
    for item in question:
        if isinstance(item, Image):
            res.append(item)
    return res
