import os

from utils.aoai import AOAIChat


def qna(prompt: str, history: list):
    max_completion_tokens = int(os.environ.get("MAX_COMPLETION_TOKENS"))

    chat = AOAIChat()
    stream = chat.stream(messages=history + [{"role": "user", "content": prompt}], max_tokens=max_completion_tokens)

    return stream
