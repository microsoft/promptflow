from promptflow.core import tool


@tool
def create_redacted_conversation(conversation: dict, pii_output: dict) -> dict:
    """
    This tool creates a conversation input for conversation-based
    language skills from the task output of conversational PII.
    It does so by replacing all original text with the PII redacted
    text.

    :param conversation: original conversation object.
    :param pii_output: conversational pii node output (parsed).
    """
    redacted_conversation = conversation.copy()
    redacted_conv_items = pii_output["conversationItems"]
    for i in range(len(redacted_conv_items)):
        redacted_text = redacted_conv_items[i]["redactedContent"]["text"]
        redacted_conversation["conversationItems"][i]["text"] = redacted_text

    return redacted_conversation
