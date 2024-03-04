from typing import List

from promptflow import tool


@tool
def criticize(words: str, chat_history: List) -> str:
    print(f"Ignoring words: {words}")
    return f"The joke is not funny, give me another one."

