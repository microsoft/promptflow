from promptflow import tool


@tool
def show_anwser(chat_answer: str):
    raise Exception("mock exception")
