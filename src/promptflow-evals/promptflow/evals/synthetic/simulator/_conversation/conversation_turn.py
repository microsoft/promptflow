# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from .constants import ConversationRole


class ConversationTurn(object):
    def __init__(self, role: ConversationRole, name=None, message="", full_response=None, request=None):
        self.role = role
        self.name = name
        self.message = message
        self.full_response = full_response
        self.request = request

    def to_openai_chat_format(self, reverse=False):
        if reverse is False:
            return {"role": self.role.value, "content": self.message}
        if self.role == ConversationRole.ASSISTANT:
            return {"role": ConversationRole.USER.value, "content": self.message}
        return {"role": ConversationRole.ASSISTANT.value, "content": self.message}

    def to_annotation_format(self, turn_number: int):
        return {
            "turn_number": turn_number,
            "response": self.message,
            "actor": self.role.value if self.name is None else self.name,
            "request": self.request,
            "full_json_response": self.full_response,
        }

    def __str__(self) -> str:
        return f"({self.role.value}): {self.message}"

    def __repr__(self) -> str:
        return f"CoversationTurn(role={self.role.value}, message={self.message})"
