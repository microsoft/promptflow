from promptflow import tool


@tool
def mock_chat(chat_history: list, question: list):
    return "Fake answer"
