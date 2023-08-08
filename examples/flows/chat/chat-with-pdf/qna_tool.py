# flake8: noqa: E402
import os
import sys

sys.path.append(f"{os.path.dirname(__file__)}/chat_with_pdf")

from promptflow import tool
from chat_with_pdf.qna import qna


@tool
def qna_tool(question: str, index_path: str, history: list):
    stream, context = qna(
        question, index_path, convert_chat_history_to_chatml_messages(history)
    )

    answer = ""
    for str in stream:
        answer = answer + str + ""

    return {"answer": answer, "context": context}


def convert_chat_history_to_chatml_messages(history):
    messages = []
    for item in history:
        messages.append({"role": "user", "content": item["inputs"]["question"]})
        messages.append({"role": "assistant", "content": item["outputs"]["answer"]})

    return messages
