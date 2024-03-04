from typing import List

from promptflow import tool


@tool
def criticize(words: str, chat_history: List, third_party_comments) -> str:
    print(f"Ignoring words: {words}")
    print(f"Ignoring third_party_comments: {third_party_comments}")
    return f"The joke is not funny, give me another one."

