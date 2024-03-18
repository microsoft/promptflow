# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path
from typing import Dict, Optional

from promptflow._constants import LANGUAGE_KEY, FlowLanguage
from promptflow._sdk._constants import BASE_PATH_CONTEXT_KEY
from promptflow._sdk.entities._validation import SchemaValidatableMixin
from promptflow.core._flow import FlexFlow as FlexFlowCore
from promptflow.exceptions import ErrorTarget, UserErrorException


class FlexFlow(FlexFlowCore, SchemaValidatableMixin):
    __doc__ = FlexFlowCore.__doc__

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

    @classmethod
    def _resolve_entry_file(cls, entry: str, working_dir: Path) -> Optional[str]:
        """Resolve entry file from entry.
        If entry is a local file, e.g. my.local.file:entry_function, return the local file: my/local/file.py
            and executor will import it from local file.
        Else, assume the entry is from a package e.g. external.module:entry, return None
            and executor will try import it from package.
        """
        try:
            entry_file = f'{entry.split(":")[0].replace(".", "/")}.py'
        except Exception as e:
            raise UserErrorException(f"Entry function {entry} is not valid: {e}")
        entry_file = working_dir / entry_file
        if entry_file.exists():
            return entry_file.resolve().absolute().as_posix()
        # when entry file not found in working directory, return None since it can come from package
        return None

    def _init_executable(self, **kwargs):
        from promptflow.batch._executor_proxy_factory import ExecutorProxyFactory
        from promptflow.contracts.flow import EagerFlow as ExecutableEagerFlow

        meta_dict = (
            ExecutorProxyFactory()
            .get_executor_proxy_cls(self.language)
            .generate_flow_json(
                flow_file=self.path,
                working_dir=self.code,
                dump=False,
            )
        )
        return ExecutableEagerFlow.deserialize(meta_dict)
