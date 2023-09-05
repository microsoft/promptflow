from promptflow import tool


@tool
def kql_retriever(content: str) -> str:
  return "KQL: " + content