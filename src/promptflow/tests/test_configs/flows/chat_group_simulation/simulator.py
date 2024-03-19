from typing import List

from promptflow import tool


@tool
def simulate(topic: str, persona: str, conversation_history: List) -> str:
    print(f"topic: {topic}")
    print(f"persona: {persona}")
    print(f"chat_history: {conversation_history}")
    return f"This is not funny, tell me another joke."

