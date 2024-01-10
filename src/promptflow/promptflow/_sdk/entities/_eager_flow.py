# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from os import PathLike
from pathlib import Path
from typing import Union

from promptflow._sdk.entities._flow import FlowBase
from promptflow.exceptions import UserErrorException


class EagerFlow(FlowBase):
    """This class is used to represent an eager flow."""

    def __init__(
        self,
        path: Union[str, PathLike],
        entry: str,
        data: dict,
        **kwargs,
    ):
        self.path = Path(path)
        self.code = self.path.parent
        self.entry = entry
        self._data = data
        super().__init__(**kwargs)

    @classmethod
    def _load(cls, path: Path, entry: str = None, data: dict = None, **kwargs):
        if entry is None:
            raise UserErrorException(f"Entry function is not specified for flow {path}")
        return cls(path=path, entry=entry, data=data, **kwargs)
