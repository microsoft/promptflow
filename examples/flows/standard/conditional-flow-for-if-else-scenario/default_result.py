from promptflow import tool


@tool
def default_result(request: str) -> str:
    return f"I'm not familiar with your query: {request}."
