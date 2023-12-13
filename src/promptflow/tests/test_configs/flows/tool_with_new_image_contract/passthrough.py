from promptflow import tool


@tool
def passthrough(question: list, chat_history: list):
    return question
