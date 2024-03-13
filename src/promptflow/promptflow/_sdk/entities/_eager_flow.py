# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path
from typing import Dict

from promptflow._constants import LANGUAGE_KEY, FlowLanguage
from promptflow._sdk._constants import BASE_PATH_CONTEXT_KEY
from promptflow._sdk.entities._validation import SchemaValidatableMixin
from promptflow.core._flow import EagerFlow as EagerFlowCore
from promptflow.exceptions import ErrorTarget, UserErrorException


class EagerFlow(EagerFlowCore, SchemaValidatableMixin):
    __doc__ = EagerFlowCore.__doc__

    # region properties
    @property
    def language(self) -> str:
        return self._data.get(LANGUAGE_KEY, FlowLanguage.Python)

    @property
    def additional_includes(self) -> list:
        return self._data.get("additional_includes", [])

    # endregion

    # region overrides
    @classmethod
    def _load(cls, path: Path, data: dict, raise_error=True, **kwargs):
        # raise validation error on unknown fields
        if raise_error:
            # Abstract here. The actual validation is done in subclass.
            data = cls._create_schema_for_validation(context={BASE_PATH_CONTEXT_KEY: path.parent}).load(data)
        return super()._load(path=path, data=data, **kwargs)

    # endregion overrides

    # region SchemaValidatableMixin
    @classmethod
    def _create_schema_for_validation(cls, context):
        # import here to avoid circular import
        from ..schemas._flow import EagerFlowSchema

        return EagerFlowSchema(context=context)

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
