from enum import Enum
from promptflow import tool


class ConversationModality(str, Enum):
    TEXT = "text"
    TRANSCRIPT = "transcript"


def create_conversation_item(line: str, id: int) -> dict:
    name_and_text = line.split(":", maxsplit=1)
    name = name_and_text[0].strip()
    text = name_and_text[1].strip()
    return {
        "id": id,
        "participantId": name,
        "role": name if name.lower() in {"customer", "agent"} else "generic",
        "text": text
    }


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
    id = 1
    lines = text.replace("  ", "\n").split("\n")
    lines = filter(lambda line: len(line.strip()) != 0, lines)
    for line in lines:
        conv_items.append(create_conversation_item(line, id))
        id += 1

    return {
        "conversationItems": conv_items,
        "language": language,
        "modality": modality,
        "id": str(id)
    }
