# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from typing import Dict

from promptflow._constants import FlowLanguage
from promptflow._sdk._constants import BASE_PATH_CONTEXT_KEY
from promptflow._sdk.entities._validation import SchemaValidatableMixin
from promptflow.core._flow import Prompty as PromptyCore
from promptflow.exceptions import ErrorTarget, UserErrorException


class Prompty(PromptyCore, SchemaValidatableMixin):
    __doc__ = PromptyCore.__doc__

    # region properties
    @property
    def language(self) -> str:
        return FlowLanguage.Python

    @property
    def additional_includes(self) -> list:
        return []

    # endregion

    # region SchemaValidatableMixin
    @classmethod
    def _create_schema_for_validation(cls, context):
        # import here to avoid circular import
        from ..schemas._flow import PromptySchema

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
