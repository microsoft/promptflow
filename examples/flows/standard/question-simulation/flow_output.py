from promptflow.core import tool


@tool
def flow_output(stop_or_continue: str, questions: str) -> str:
    if "stop" in stop_or_continue.lower():
        return "[STOP]"
    else:
        return questions
