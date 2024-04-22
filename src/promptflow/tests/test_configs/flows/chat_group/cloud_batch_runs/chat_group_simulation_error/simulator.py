import uuid
from typing import List

from promptflow import tool


@tool
def simulate(question: str, ground_truth: str, conversation_history: List) -> str:
    print(f"question: {question}")
    print(f"chat_history: {conversation_history}")
    generated_question = get_question_from_conversation_history(conversation_history, question)
    print(f"generated_question: {generated_question}")
    if generated_question != ground_truth:
        return generated_question
    else:
        return "[STOP]"