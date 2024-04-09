from promptflow.core import tool


@tool
def icm_retriever(content: str) -> str:
  return "ICM: " + content