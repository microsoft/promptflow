# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from os import PathLike
from pathlib import Path
from typing import Dict, Union

from promptflow._constants import LANGUAGE_KEY, FlowLanguage
from promptflow._sdk._constants import BASE_PATH_CONTEXT_KEY
from promptflow.core._flow import Prompty as CorePrompty
from promptflow.exceptions import ErrorTarget, UserErrorException

from .base import FlowBase


class Prompty(FlowBase):
    __doc__ = CorePrompty.__doc__

    def __init__(
        self,
        path: Union[str, PathLike],
        code: Union[str, PathLike],
        data: dict,
        **kwargs,
    ):
        # prompty file path
        path = Path(path)
        # prompty folder path
        code = Path(code)
        self._flow_file_path = path
        self._core_prompty = CorePrompty(path=path, **kwargs)
        super().__init__(code=code, path=path, data=data, content_hash=None, **kwargs)

    @property
    def name(self) -> str:
        return self.code.name

    @property
    def language(self) -> str:
        return self._data.get(LANGUAGE_KEY, FlowLanguage.Python)

    @property
    def sample(self):
        return self._data.get("sample", None)

    # region overrides

    @classmethod
    def _load(cls, path: Path, raise_error=True, **kwargs):
        core_prompty = CorePrompty(path=path, **kwargs)
        # raise validation error on unknown fields
        if raise_error:
            from marshmallow import INCLUDE

            # Abstract here. The actual validation is done in subclass.
            data = cls._create_schema_for_validation(context={BASE_PATH_CONTEXT_KEY: path.parent}).load(
                core_prompty._data, unknown=INCLUDE
            )
        return cls(path=path, code=path.parent, data=data, **kwargs)

    def __call__(self, *args, **kwargs):
        return self._core_prompty(*args, **kwargs)

    # endregion overrides

    # region SchemaValidatableMixin
    @classmethod
    def _create_schema_for_validation(cls, context):
        # import here to avoid circular import
        from promptflow._sdk.schemas._flow import PromptySchema

        return PromptySchema(context=context)

    def _default_context(self) -> dict:
        return {BASE_PATH_CONTEXT_KEY: self.code}

    def _create_validation_error(self, message, no_personal_data_message=None):
        return UserErrorException(
            message=message,
            target=ErrorTarget.CONTROL_PLANE_SDK,
            no_personal_data_message=no_personal_data_message,
        )

    def _dump_for_validation(self) -> Dict:
        # Flow is read-only in control plane, so we always dump the flow from file
        return self._data

    # endregion SchemaValidatableMixin
