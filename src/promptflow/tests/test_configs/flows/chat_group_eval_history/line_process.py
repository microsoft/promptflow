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
def line_process(ground_truth: str, conversation_history: List):
    """
    This tool processes the prediction of a single line and returns the processed result.

    :param groundtruth: the groundtruth of a single line.
    :param prediction: the prediction of a single line.
    """
    answer = get_answer_from_conversation_history(conversation_history)
    # Add your line processing logic here
    return "Correct" if ground_truth.lower() == answer.lower() else "Incorrect"
