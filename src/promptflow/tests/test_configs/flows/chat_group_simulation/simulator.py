from typing import List

from promptflow.core import tool


def get_answer_from_conversation_history(conversation_history: List) -> str:
    """
    This function gets the answer from the conversation history.

    :param conversation_history: the conversation history.
    """
    if len(conversation_history) == 0:
        return "NA"
    assistant_answers = [item[1] for item in conversation_history if item[0] == "assistant"]
    return assistant_answers[-1]["output"]


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

