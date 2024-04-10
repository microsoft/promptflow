from promptflow.core import tool


@tool
def my_python_tool(answer_question_prompt: str, refuse_prompt: str, not_relevant: bool) -> str:
    if not_relevant:
        return refuse_prompt

    return answer_question_prompt
