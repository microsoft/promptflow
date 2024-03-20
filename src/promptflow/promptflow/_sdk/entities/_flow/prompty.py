# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from os import PathLike
from pathlib import Path
from typing import Dict, Union

from promptflow._constants import FlowLanguage
from promptflow._sdk._constants import BASE_PATH_CONTEXT_KEY
from promptflow.exceptions import ErrorTarget, UserErrorException

from .base import FlowBase


class Prompty(FlowBase):
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
        super().__init__(code=code, path=path, data=data, content_hash=None, **kwargs)

    # region overrides

    @property
    def language(self) -> str:
        return FlowLanguage.Python

    @property
    def additional_includes(self) -> list:
        return []

    @classmethod
    def _load(cls, path: Path, raise_error=True, **kwargs):
        from promptflow.core._flow import Prompty as CorePrompty

        core_prompty = CorePrompty(path=path, **kwargs)
        # raise validation error on unknown fields
        if raise_error:
            from marshmallow import INCLUDE

            # Abstract here. The actual validation is done in subclass.
            data = cls._create_schema_for_validation(context={BASE_PATH_CONTEXT_KEY: path.parent}).load(
                core_prompty._data, unknown=INCLUDE
            )
        return cls(path=path, code=path.parent, data=data, **kwargs)

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
