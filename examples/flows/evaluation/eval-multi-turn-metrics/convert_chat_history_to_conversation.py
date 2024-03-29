from promptflow.core import tool


@tool
def convert_chat_history_to_conversation(chat_history: list) -> dict:
    conversation = ""
    for i in chat_history:
        conversation += f"User: {i['inputs']['question']}\nBot: {i['outputs']['answer']}\n"
    conversation_format = {"conversation": conversation}
    return conversation_format
