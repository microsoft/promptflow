from promptflow.core import tool


@tool
def retriever_summary(summary) -> str:
    print(f"Summary: {summary}")
    return "Execute incident info extractor"
