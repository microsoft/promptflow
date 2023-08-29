from dataclasses import dataclass
from promptflow.contracts.types import Secret
from promptflow._core.tools_manager import register_connections


@dataclass
class MyFirstConnection():
    api_key: Secret
    api_hint: str = "This is my first connection."


@dataclass
class MySecondConnection():
    api_key: Secret
    api_hint: str = "This is my second connection."


register_connections([MyFirstConnection, MySecondConnection])
