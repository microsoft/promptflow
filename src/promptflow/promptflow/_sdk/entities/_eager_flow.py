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
        code: Union[str, PathLike],
        entry: str,
        data: dict,
        **kwargs,
    ):
        # flow.dag.yaml file path or entry.py file path
        path = Path(path)
        # flow.dag.yaml file's folder or entry.py's folder
        code = Path(code)
        # entry function name
        self.entry = entry
        # TODO(2910062): support eager flow execution cache
        super().__init__(data=data, path=path, code=code, content_hash=None, **kwargs)

    @property
    def language(self) -> str:
        return self._data.get(LANGUAGE_KEY, FlowLanguage.Python)

    @property
    def additional_includes(self) -> list:
        return self._data.get("additional_includes", [])

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
        code = path.parent

        if entry is None:
            raise UserErrorException(f"Entry function is not specified for flow {path}")
        return cls(path=path, code=code, entry=entry, data=data, **kwargs)
