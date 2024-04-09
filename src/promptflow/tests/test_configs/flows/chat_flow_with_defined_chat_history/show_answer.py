from promptflow.core import tool


@tool
def show_answer(chat_answer: str):
    print("print:", chat_answer)
    return chat_answer
