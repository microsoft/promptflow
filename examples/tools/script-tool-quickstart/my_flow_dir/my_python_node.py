from promptflow import tool
from dataclasses import dataclass
from promptflow.contracts.types import Secret
from promptflow._core.tools_manager import register_connections


@dataclass
class MyCustomConnection():
    api_key: Secret
    api_hint: str = "This is my custom connection."


register_connections([MyCustomConnection])


@tool
def my_python_tool(input1: str, connection: MyCustomConnection) -> str:
    return input1 + connection.api_hint
