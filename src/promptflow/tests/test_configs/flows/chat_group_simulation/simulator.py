from typing import List

from promptflow import tool


def get_answer_from_conversation_history(conversation_history: List) -> str:
    return "answer from conversation history"


@tool
def simulate(question: str, ground_truth: str, conversation_history: List) -> str:
    print(f"question: {question}")
    print(f"chat_history: {conversation_history}")
    answer = get_answer_from_conversation_history(conversation_history)
    print(f"answer: {answer}")
    if answer != ground_truth:
        return "I don't like this answer, give me another one."
    else:
        return "[STOP]"

