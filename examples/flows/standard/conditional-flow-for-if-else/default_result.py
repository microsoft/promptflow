from promptflow.core import tool


@tool
def default_result(question: str) -> str:
    return f"I'm not familiar with your query: {question}."
