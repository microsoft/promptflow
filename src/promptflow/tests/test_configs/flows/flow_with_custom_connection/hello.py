from promptflow.core import tool
from promptflow.connections import CustomConnection


@tool
def my_python_tool1(text: str, connection: CustomConnection) -> dict:
    return dict(connection)

