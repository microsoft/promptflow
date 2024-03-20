# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from os import PathLike
from pathlib import Path
from typing import Dict, Optional, Union

from promptflow._constants import LANGUAGE_KEY, FlowLanguage
from promptflow._sdk._constants import BASE_PATH_CONTEXT_KEY
from promptflow._utils.flow_utils import resolve_entry_file
from promptflow.exceptions import ErrorTarget, UserErrorException

from .dag import Flow


class FlexFlow(Flow):
    """A FlexFlow represents a flow defined with codes directly. It doesn't involve a directed acyclic graph (DAG)
    explicitly, but its entry function haven't been provided.
    FlexFlow basically behave like a Flow.
    Load of this non-dag flow is provided, but direct call of it will cause exceptions.
    """

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
        # entry file name
        self.entry_file = resolve_entry_file(entry=entry, working_dir=code)
        # TODO(2910062): support non-dag flow execution cache
        super().__init__(code=code, path=path, dag=data, content_hash=None, **kwargs)

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

        entry = data.get("entry")
        code = path.parent

        if entry is None:
            raise UserErrorException(f"Entry function is not specified for flow {path}")
        return cls(path=path, code=code, entry=entry, data=data, **kwargs)

    # endregion overrides

    # region SchemaValidatableMixin
    @classmethod
    def _create_schema_for_validation(cls, context):
        # import here to avoid circular import
        from promptflow._sdk.schemas._flow import EagerFlowSchema

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
        # TODO(2991934): support environment variables here
        from promptflow._proxy import ProxyFactory
        from promptflow.contracts.flow import EagerFlow as ExecutableEagerFlow

        meta_dict = (
            ProxyFactory()
            .get_executor_proxy_cls(self.language)
            .generate_flow_json(
                flow_file=self.path,
                working_dir=self.code,
                dump=False,
            )
        )
        return ExecutableEagerFlow.deserialize(meta_dict)

    def __call__(self, *args, **kwargs):
        """Direct call of non-dag flow WILL cause exceptions."""
        raise UserErrorException("FlexFlow can not be called as a function.")
