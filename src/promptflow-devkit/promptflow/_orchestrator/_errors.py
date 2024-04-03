# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from promptflow.exceptions import UserErrorException


class InvalidChatRoleCount(UserErrorException):
    pass


class MissingConversationHistoryExpression(UserErrorException):
    pass


class MultipleConversationHistoryInputsMapping(UserErrorException):
    pass


class UsingReservedRoleKey(UserErrorException):
    pass


class InvalidMaxTurnValue(UserErrorException):
    pass
