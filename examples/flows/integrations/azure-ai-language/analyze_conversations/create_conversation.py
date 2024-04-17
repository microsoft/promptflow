from enum import Enum
from promptflow.core import tool

MAX_CONV_ITEM_LEN = 1000


class ConversationModality(str, Enum):
    TEXT = "text"
    TRANSCRIPT = "transcript"


def create_conversation_item(name: str, text: str) -> dict:
    return {
        "participantId": name,
        "role": name if name.lower() in {"customer", "agent"} else "generic",
        "text": text
    }


def parse_conversation_line(line: str) -> list[dict]:
    name_and_text = line.split(":", maxsplit=1)
    name = name_and_text[0].strip()
    text = name_and_text[1].strip()
    conv_items = []
    sentences = [s.strip() for s in text.split(".")]
    buffer = ""

    for sentence in sentences:
        if len(buffer.strip()) + len(sentence) + 2 >= MAX_CONV_ITEM_LEN:
            conv_items.append(create_conversation_item(name, buffer.strip()))
            buffer = ""
        buffer += " " + sentence + "."

    conv_items.append(create_conversation_item(name, buffer.strip()))
    return conv_items


@tool
def create_conversation(text: str,
                        modality: ConversationModality,
                        language: str,
                        id: int) -> dict:
    """
    This tool creates a conversation input for conversation-based
    language skills.

    Conversation text is assumed to be of the following form:
    <speaker id>: <speaker text>
    <speaker id>: <speaker text>
    ...

    :param text: conversation text.
    :param modality: conversation modality.
    :param language: conversation language.
    :param id: conversation id.
    """
    conv_items = []
    id = 0
    lines = text.replace("  ", "\n").split("\n")
    lines = filter(lambda line: len(line.strip()) != 0, lines)
    for line in lines:
        for conv_item in parse_conversation_line(line):
            id += 1
            conv_item["id"] = id
            conv_items.append(conv_item)

    return {
        "conversationItems": conv_items,
        "language": language,
        "modality": modality,
        "id": str(id)
    }
