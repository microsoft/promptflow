# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from dataclasses import dataclass


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
    """This class is used to hint a parameter is an assistant override."""

    def __init__(self, model: str, instructions: str, tools: list):
        self.model = model
        self.instructions = instructions
        self.tools = tools

    @staticmethod
    def deserialize(data: dict) -> "AssistantDefinition":
        return AssistantDefinition(
            model=data.get("module"),
            instructions=data.get("instructions"),
            tools=data.get("tools")
        )

    def serialize(self):
        return {
            "module": self.model,
            "instructions": self.instructions,
            "tools": self.tools,
        }
