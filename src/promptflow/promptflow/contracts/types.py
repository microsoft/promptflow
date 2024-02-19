# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from dataclasses import dataclass, field
from typing import Callable, Dict, List


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
class AssistantTool:
    name: str
    openai_definition: dict
    func: Callable


@dataclass
class AssistantDefinition:
    """This class is used to define an assistant definition."""

    model: str
    instructions: str
    tools: List  # The raw tool definition
    assistant_tools: Dict[str, AssistantTool] = field(default_factory=dict)  # The resolved tool definition by name

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

    def init_tool_invoker(self):
        from promptflow.executor._assistant_tool_invoker import AssistantToolInvoker

        return AssistantToolInvoker.init(self)
