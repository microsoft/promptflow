# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# pylint: disable=C0103,C0114,C0116
from dataclasses import dataclass
from typing import Union

from promptflow.evals.synthetic._conversation.constants import ConversationRole


@dataclass
class Turn:
    """
    Represents a conversation turn,
    keeping track of the role, content,
    and context of a turn in a conversation.
    """

    role: Union[str, ConversationRole]
    content: str
    context: str = None

    def to_dict(self):
        """
        Convert the conversation turn to a dictionary.

        Returns:
            dict: A dictionary representation of the conversation turn.
        """
        return {
            "role": self.role.value if isinstance(self.role, ConversationRole) else self.role,
            "content": self.content,
            "context": self.context,
        }

    def __repr__(self):
        """
        Return the string representation of the conversation turn.

        Returns:
            str: A string representation of the conversation turn.
        """
        return f"Turn(role={self.role}, content={self.content})"


class ConversationHistory:
    """
    Conversation history class to keep track of the conversation turns in a conversation.
    """

    def __init__(self):
        """
        Initializes the conversation history with an empty list of turns.
        """
        self.history = []

    def add_to_history(self, turn: Turn):
        """
        Adds a turn to the conversation history.

        Args:
            turn (Turn): The conversation turn to add.
        """
        self.history.append(turn)

    def to_list(self):
        """
        Converts the conversation history to a list of dictionaries.

        Returns:
            list: A list of dictionaries representing the conversation turns.
        """
        return [turn.to_dict() for turn in self.history]

    def get_length(self):
        """
        Returns the length of the conversation.

        Returns:
            int: The number of turns in the conversation history.
        """
        return len(self.history)

    def __repr__(self):
        """
        Returns the string representation of the conversation history.

        Returns:
            str: A string representation of the conversation history.
        """
        for turn in self.history:
            print(turn)
        return ""
