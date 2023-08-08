# flake8: noqa: E402
import os
import sys

sys.path.append(f"{os.path.dirname(__file__)}/chat_with_pdf")

from promptflow import tool
from chat_with_pdf.rewrite_question import rewrite_question


@tool
def rewrite_question_tool(question: str, history: list):
    return rewrite_question(question, history)
