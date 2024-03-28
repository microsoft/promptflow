# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from collections import UserDict
from typing import Any

from promptflow._sdk._errors import UnexpectedAttributeError


class AttrDict(UserDict):
    def __init__(self, inputs: dict, **kwargs: Any):
        super().__init__(**inputs, **kwargs)

    def __getattr__(self, item: Any):
        return self.__getitem__(item)

    def __getitem__(self, item: Any):
        if item not in self:
            raise UnexpectedAttributeError(f"Invalid attribute {item!r}, expected one of {list(self.keys())}.")
        res = super().__getitem__(item)
        return res


class ChatRoleInputs(AttrDict):
    """Chat role inputs"""


class ChatRoleOutputs(AttrDict):
    """Chat role outputs"""


class ChatGroupInputs(AttrDict):
    """Chat group inputs"""


class ChatGroupOutputs(AttrDict):
    """Chat group outputs"""
