# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from dataclasses import dataclass
from typing import Any, List


class Secret(str):
    """This class is used to hint a parameter is a secret to load."""

    def set_secret_name(self, name):
        """Set the secret_name attribute for the Secret instance.

        :param name: The name of the secret.
        :type name: str
        """
        self.secret_name = name


class PromptTemplate(str):
    """This class is used to hint a parameter is a prompt template."""

    pass


class FilePath(str):
    """This class is used to hint a parameter is a file path."""

    pass


@dataclass
class AssistantDefinition:
    """This class is used to define an assistant definition."""

    model: str
    instructions: str
    tools: List  # The raw tool definition in json string

    @staticmethod
    def deserialize(data: dict) -> "AssistantDefinition":
        return AssistantDefinition(
            model=data.get("model", ""), instructions=data.get("instructions", ""), tools=data.get("tools", [])
        )

    def serialize(self):
        return {
            "model": self.model,
            "instructions": self.instructions,
            "tools": self.tools,
        }

    def __post_init__(self):
        # Implicitly introduce the '_tool_invoker' attribute here
        self._tool_invoker = None  # reserved attribute for tool invoker injection


class AttrDict(dict):
    """A dictionary that allows attribute access to its keys."""

    def __getattr__(self, key: str) -> Any:
        return self[key]

    def __setattr__(self, key: str, value: Any) -> None:
        self[key] = value
