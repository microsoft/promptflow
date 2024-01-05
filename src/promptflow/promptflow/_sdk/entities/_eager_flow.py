# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from os import PathLike
from pathlib import Path
from typing import Union

from promptflow._sdk.entities._flow import FlowBase, FlowContext
from promptflow.exceptions import UserErrorException


class EagerFlow(FlowBase):
    """This class is used to represent a flow."""

    def __init__(
        self,
        code: Union[str, PathLike],
        **kwargs,
    ):
        self.code = Path(code)
        # TODO: put flow context in base?
        self._context = FlowContext()
        super().__init__(**kwargs)

    @property
    def context(self) -> FlowContext:
        return self._context

    @context.setter
    def context(self, val):
        if not isinstance(val, FlowContext):
            raise UserErrorException("context must be a FlowContext object, got {type(val)} instead.")
        self._context = val

    @property
    def path(self):
        return self.code / "entry.py"

    @classmethod
    def _load(cls, flow_path, **kwargs):
        return cls(code=Path(flow_path).parent)
