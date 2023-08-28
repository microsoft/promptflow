from promptflow import tool
from chat_with_pdf.qna import qna


@tool
def qna_tool(prompt: str, history: list):
    stream = qna(prompt, convert_chat_history_to_chatml_messages(history))

    answer = ""
    for str in stream:
        answer = answer + str + ""

    return {"answer": answer}


def convert_chat_history_to_chatml_messages(history):
    messages = []
    for item in history:
        messages.append({"role": "user", "content": item["inputs"]["question"]})
        messages.append({"role": "assistant", "content": item["outputs"]["answer"]})

    return messages
