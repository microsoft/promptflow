# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import abc
import logging
from os import PathLike
from pathlib import Path
from typing import Dict, Tuple, Union

import yaml
from marshmallow import Schema

from promptflow._sdk._constants import (
    BASE_PATH_CONTEXT_KEY,
    DEFAULT_ENCODING,
    FLOW_TOOLS_JSON,
    LOGGER_NAME,
    PROMPT_FLOW_DIR_NAME,
)
from promptflow.exceptions import ErrorTarget, UserErrorException

from .._constants import DAG_FILE_NAME
from ._validation import SchemaValidatableMixin

logger = logging.getLogger(LOGGER_NAME)


class FlowBase(abc.ABC):
    @classmethod
    # pylint: disable=unused-argument
    def _resolve_cls_and_type(cls, data, params_override):
        """Resolve the class to use for deserializing the data. Return current class if no override is provided.
        :param data: Data to deserialize.
        :type data: dict
        :param params_override: Parameters to override, defaults to None
        :type params_override: typing.Optional[list]
        :return: Class to use for deserializing the data & its "type". Type will be None if no override is provided.
        :rtype: tuple[class, typing.Optional[str]]
        """
        return cls, "flow"


class FlowContext:
    def __init__(self, connections=None, connection_provider=None, variant=None):
        # TODO: make this a context manager
        # TODO: support other configs to inject when executing flow?
        self.connections = connections
        self.connection_provider = connection_provider
        self.variant = variant


class Flow(FlowBase):
    """This class is used to represent a flow."""

    def __init__(
        self,
        code: str,
        **kwargs,
    ):
        self._code = Path(code)
        path = kwargs.pop("path", None)
        self._path = Path(path) if path else None
        self._context = FlowContext()
        self.variant = kwargs.pop("variant", None) or {}
        super().__init__(**kwargs)

    @property
    def code(self) -> Path:
        return self._code

    @code.setter
    def code(self, value: Union[str, PathLike, Path]):
        self._code = value

    @property
    def path(self) -> Path:
        flow_file = self._path or self.code / DAG_FILE_NAME
        if not flow_file.is_file():
            raise UserErrorException(
                "The directory does not contain a valid flow.",
                target=ErrorTarget.CONTROL_PLANE_SDK,
            )
        return flow_file

    @property
    def context(self) -> FlowContext:
        return self._context

    @classmethod
    def load(
        cls,
        source: Union[str, PathLike],
        **kwargs,
    ):
        source_path = Path(source)
        if not source_path.exists():
            raise Exception(f"Source {source_path.absolute().as_posix()} does not exist")
        if source_path.is_dir() and (source_path / DAG_FILE_NAME).is_file():
            return cls(code=source_path.absolute().as_posix(), **kwargs)
        elif source_path.is_file() and source_path.name == DAG_FILE_NAME:
            # TODO: for file, we should read the yaml to get code and set path to source_path
            return cls(code=source_path.absolute().parent.as_posix(), **kwargs)

        raise Exception("source must be a directory or a flow.dag.yaml file")

    def _init_executable(self, tuning_node=None, variant=None):
        from promptflow._sdk.operations._run_submitter import variant_overwrite_context

        # TODO: check if there is potential bug here
        # this is a little wired:
        # 1. the executable is created from a temp folder when there is additional includes
        # 2. after the executable is returned, the temp folder is deleted
        with variant_overwrite_context(self.code, tuning_node, variant) as flow:
            from promptflow.contracts.flow import Flow as ExecutableFlow

            return ExecutableFlow.from_yaml(flow_file=flow.path, working_dir=flow.code)


class ProtectedFlow(Flow, SchemaValidatableMixin):
    """This class is used to hide internal interfaces from user.

    User interface should be carefully designed to avoid breaking changes, while developers may need to change internal
    interfaces to improve the code quality. On the other hand, making all internal interfaces private will make it
    strange to use them everywhere inside this package.

    Ideally, developers should always initialize ProtectedFlow object instead of Flow object.
    """

    def __init__(
        self,
        code: str,
        **kwargs,
    ):
        super().__init__(code=code, **kwargs)

        self._flow_dir, self._dag_file_name = self._get_flow_definition(self.code)
        self._executable = None

    @property
    def flow_dag_path(self) -> Path:
        return self._flow_dir / self._dag_file_name

    @property
    def name(self) -> str:
        return self._flow_dir.name

    @property
    def tools_meta_path(self) -> Path:
        target_path = self._flow_dir / PROMPT_FLOW_DIR_NAME / FLOW_TOOLS_JSON
        target_path.parent.mkdir(parents=True, exist_ok=True)
        return target_path

    @classmethod
    def _get_flow_definition(cls, flow, base_path=None) -> Tuple[Path, str]:
        if base_path:
            flow_path = Path(base_path) / flow
        else:
            flow_path = Path(flow)

        if flow_path.is_dir() and (flow_path / DAG_FILE_NAME).is_file():
            return flow_path, DAG_FILE_NAME
        elif flow_path.is_file():
            return flow_path.parent, flow_path.name

        raise ValueError(f"Can't find flow with path {flow_path.as_posix()}.")

    # region SchemaValidatableMixin
    @classmethod
    def _create_schema_for_validation(cls, context) -> Schema:
        # import here to avoid circular import
        from ..schemas._flow import FlowSchema

        return FlowSchema(context=context)

    def _default_context(self) -> dict:
        return {BASE_PATH_CONTEXT_KEY: self._flow_dir}

    def _create_validation_error(self, message, no_personal_data_message=None):
        return UserErrorException(
            message=message,
            target=ErrorTarget.CONTROL_PLANE_SDK,
            no_personal_data_message=no_personal_data_message,
        )

    def _dump_for_validation(self) -> Dict:
        # Flow is read-only in control plane, so we always dump the flow from file
        return yaml.safe_load(self.flow_dag_path.read_text(encoding=DEFAULT_ENCODING))

    # endregion

    # region MLFlow model requirements
    @property
    def inputs(self):
        # This is used for build mlflow model signature.
        if not self._executable:
            self._executable = self._init_executable()
        return {k: v.type.value for k, v in self._executable.inputs.items()}

    @property
    def outputs(self):
        # This is used for build mlflow model signature.
        if not self._executable:
            self._executable = self._init_executable()
        return {k: v.type.value for k, v in self._executable.outputs.items()}

    # endregion

    def __call__(self, *args, **kwargs):
        # run flow test here
        # TODO: cache the submitter?
        from promptflow import PFClient
        from promptflow._sdk.operations._test_submitter import TestSubmitter

        if args:
            raise UserErrorException("Flow can only be called with keyword arguments.")
        client = PFClient()
        # TODO: put flow context related code
        result = client.flows._test_flow(flow=self, inputs=kwargs, variant=self.variant)
        TestSubmitter._raise_error_when_test_failed(result, show_trace=False)
        return result.output
