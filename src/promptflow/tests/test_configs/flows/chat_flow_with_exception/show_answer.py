from promptflow.core import tool


@tool
def show_answer(chat_answer: str):
    raise Exception("mock exception")
