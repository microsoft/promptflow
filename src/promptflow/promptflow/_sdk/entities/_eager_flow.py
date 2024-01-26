# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from os import PathLike
from pathlib import Path
from typing import Union

from promptflow._constants import LANGUAGE_KEY, FlowLanguage
from promptflow._sdk._constants import BASE_PATH_CONTEXT_KEY
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

    @property
    def language(self) -> str:
        return self._data.get(LANGUAGE_KEY, FlowLanguage.Python)

    @classmethod
    def _create_schema_for_validation(cls, context):
        # import here to avoid circular import
        from ..schemas._flow import EagerFlowSchema

        return EagerFlowSchema(context=context)

    @classmethod
    def _load(cls, path: Path, data: dict, **kwargs):
        # schema validation on unknown fields
        data = cls._create_schema_for_validation(context={BASE_PATH_CONTEXT_KEY: path.parent}).load(data)
        entry = data["entry"]

        if entry is None:
            raise UserErrorException(f"Entry function is not specified for flow {path}")
        return cls(path=path, entry=entry, data=data, **kwargs)
