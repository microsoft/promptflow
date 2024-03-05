from typing import List

from promptflow import tool


@tool
def criticize(words: str, third_party_comments: str, chat_history: List) -> str:
    print(f"Ignoring words: {words}")
    print(f"Ignoring third_party_comments: {third_party_comments}")
    print(f"Ignoring chat_history: {chat_history}")
    return f"The joke is not funny, give me another one."

