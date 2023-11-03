from promptflow import tool
from promptflow.connections import CustomConnection


@tool
def my_python_tool(text: str, connection: CustomConnection) -> dict:
    return connection._to_dict()

