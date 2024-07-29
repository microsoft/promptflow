# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# pylint: disable=C4739,C4741,C4742
from promptflow.evals.synthetic._conversation.constants import ConversationRole


class ConvTurn:
    """
    Represents a conversation turn,
    keeping track of the role, content,
    and context of a turn in a conversation.
    """

    def __init__(self, role, content, context=None):
        """
        Initialize the conversation turn with the role, content, and context.

        Args:
            role (str or ConversationRole): The role of the participant in the conversation.
            content (str): The content of the conversation turn.
            context (optional): Additional context for the conversation turn. Defaults to None.
        """
        self.role = role
        self.content = content
        self.context = context

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
        return f"ConvTurn(role={self.role}, content={self.content})"


class ConvHistory:
    """
    Conversation history class to keep track of the conversation turns in a conversation.
    """

    def __init__(self):
        """
        Initializes the conversation history with an empty list of turns.
        """
        self.history = []

    def add_to_history(self, turn):
        """
        Adds a turn to the conversation history.

        Args:
            turn (ConvTurn): The conversation turn to add.
        """
        self.history.append(turn)

    def to_conv_history(self):
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
