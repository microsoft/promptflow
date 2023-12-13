# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import abc
import json
from os import PathLike
from pathlib import Path
from typing import Dict, Tuple, Union

import yaml
from marshmallow import Schema

from promptflow._constants import LANGUAGE_KEY, FlowLanguage
from promptflow._sdk._constants import (
    BASE_PATH_CONTEXT_KEY,
    DEFAULT_ENCODING,
    FLOW_TOOLS_JSON,
    LOGGER_NAME,
    PROMPT_FLOW_DIR_NAME,
)
from promptflow.exceptions import ErrorTarget, UserErrorException

from ..._utils.flow_utils import resolve_flow_path
from ..._utils.logger_utils import LoggerFactory
from .._constants import DAG_FILE_NAME
from ._connection import _Connection
from ._validation import SchemaValidatableMixin

logger = LoggerFactory.get_logger(LOGGER_NAME)


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
    """Flow context entity. the settings on this context will be applied to the flow when executing.

    :param connections: Connections for the flow.
    :type connections: Optional[Dict[str, Dict]]
    :param variant: Variant of the flow.
    :type variant: Optional[str]
    :param variant: Overrides of the flow.
    :type variant: Optional[Dict[str, Dict]]
    :param streaming: Whether the flow's output need to be return in streaming mode.
    :type streaming: Optional[bool]
    """

    def __init__(
        self,
        *,
        connections=None,
        variant=None,
        overrides=None,
        streaming=None,
    ):
        self.connections, self._connection_objs = connections or {}, {}
        self.variant = variant
        self.overrides = overrides or {}
        self.streaming = streaming
        # TODO: introduce connection provider support

    def _resolve_connections(self):
        # resolve connections and create placeholder for connection objects
        for _, v in self.connections.items():
            if isinstance(v, dict):
                for k, conn in v.items():
                    if isinstance(conn, _Connection):
                        name = self._get_connection_obj_name(conn)
                        v[k] = name
                        self._connection_objs[name] = conn

    @classmethod
    def _get_connection_obj_name(cls, connection: _Connection):
        # create a unique connection name for connection obj
        # will generate same name if connection has same content
        connection_dict = connection._to_dict()
        connection_name = f"connection_{hash(json.dumps(connection_dict, sort_keys=True))}"
        return connection_name

    def _to_dict(self):
        return {
            "connections": self.connections,
            "variant": self.variant,
            "overrides": self.overrides,
            "streaming": self.streaming,
        }

    def __eq__(self, other):
        if isinstance(other, FlowContext):
            return self._to_dict() == other._to_dict()
        return False

    def __hash__(self):
        self._resolve_connections()
        return hash(json.dumps(self._to_dict(), sort_keys=True))


class Flow(FlowBase):
    """This class is used to represent a flow."""

    def __init__(
        self,
        code: Union[str, PathLike],
        dag: dict,
        **kwargs,
    ):
        self._code = Path(code)
        path = kwargs.pop("path", None)
        self._path = Path(path) if path else None
        self._context = FlowContext()
        self.variant = kwargs.pop("variant", None) or {}
        self._content_hash = kwargs.pop("content_hash", None)
        self.dag = dag
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

    @context.setter
    def context(self, val):
        if not isinstance(val, FlowContext):
            raise UserErrorException("context must be a FlowContext object, got {type(val)} instead.")
        self._context = val

    @classmethod
    def load(
        cls,
        source: Union[str, PathLike],
        **kwargs,
    ):
        source_path = Path(source)
        if not source_path.exists():
            raise UserErrorException(f"Source {source_path.absolute().as_posix()} does not exist")

        flow_path = resolve_flow_path(source_path)
        if flow_path.exists():
            # TODO: for file, we should read the yaml to get code and set path to source_path
            # read flow file to get hash
            with open(flow_path, "r", encoding=DEFAULT_ENCODING) as f:
                flow_content = f.read()
                flow_dag = yaml.safe_load(flow_content)
                kwargs["content_hash"] = hash(flow_content)
            return cls(code=flow_path.parent.absolute().as_posix(), dag=flow_dag, **kwargs)

        raise UserErrorException("Source must be a directory or a 'flow.dag.yaml' file")

    def _init_executable(self, tuning_node=None, variant=None):
        from promptflow._sdk._submitter import variant_overwrite_context

        # TODO: check if there is potential bug here
        # this is a little wired:
        # 1. the executable is created from a temp folder when there is additional includes
        # 2. after the executable is returned, the temp folder is deleted
        with variant_overwrite_context(self.code, tuning_node, variant) as flow:
            from promptflow.contracts.flow import Flow as ExecutableFlow

            return ExecutableFlow.from_yaml(flow_file=flow.path, working_dir=flow.code)

    def __eq__(self, other):
        if isinstance(other, Flow):
            return self._content_hash == other._content_hash and self.context == other.context
        return False

    def __hash__(self):
        return hash(self.context) ^ self._content_hash


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
    def display_name(self) -> str:
        return self.dag.get("display_name", None)

    @property
    def language(self) -> str:
        return self.dag.get(LANGUAGE_KEY, FlowLanguage.Python)

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
        """Calling flow as a function, the inputs should be provided with key word arguments.
        Returns the output of the flow.
        The function call throws UserErrorException: if the flow is not valid or the inputs are not valid.
        SystemErrorException: if the flow execution failed due to unexpected executor error.

        :param args: positional arguments are not supported.
        :param kwargs: flow inputs with key word arguments.
        :return:
        """

        if args:
            raise UserErrorException("Flow can only be called with keyword arguments.")

        result = self.invoke(inputs=kwargs)
        return result.output

    def invoke(self, inputs: dict) -> "LineResult":
        """Invoke a flow and get a LineResult object."""
        from promptflow._sdk._submitter.test_submitter import TestSubmitterViaProxy
        from promptflow._sdk.operations._flow_context_resolver import FlowContextResolver

        if self.dag.get(LANGUAGE_KEY, FlowLanguage.Python) == FlowLanguage.CSharp:
            with TestSubmitterViaProxy(flow=self, flow_context=self.context).init() as submitter:
                result = submitter.exec_with_inputs(
                    inputs=inputs,
                )
                return result
        else:

            invoker = FlowContextResolver.resolve(flow=self)
            result = invoker._invoke(
                data=inputs,
            )
            return result
