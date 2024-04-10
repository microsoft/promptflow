from promptflow.core import tool
from promptflow.contracts.multimedia import Image


@tool
def mock_chat(chat_history: list, question: list):
    ensure_image_in_list(question, "question")
    for item in chat_history:
        ensure_image_in_list(item["inputs"]["question"], "inputs of chat history")
        ensure_image_in_list(item["outputs"]["answer"], "outputs of chat history")
    res = []
    for item in question:
        if isinstance(item, Image):
            res.append(item)
    res.append("text response")
    return res


def ensure_image_in_list(value: list, name: str):
    include_image = False
    for item in value:
        if isinstance(item, Image):
            include_image = True
    if not include_image:
        raise Exception(f"No image found in {name}, you should include at least one image in your {name}.")
