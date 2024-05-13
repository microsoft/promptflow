# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
from os import PathLike
from pathlib import Path
from typing import Union

from promptflow._constants import DEFAULT_ENCODING, FLOW_FILE_SUFFIX
from promptflow._sdk.entities._validation import SchemaValidatableMixin
from promptflow._utils.flow_utils import is_flex_flow, is_prompty_flow, resolve_flow_path
from promptflow._utils.yaml_utils import load_yaml_string
from promptflow.core._flow import AbstractFlowBase
from promptflow.exceptions import UserErrorException


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
                    # TODO: avoid this import
                    from promptflow.core._connection import _Connection

                    if isinstance(conn, _Connection):  # Core COnnection
                        name = self._get_connection_obj_name(conn)
                        v[k] = name
                        self._connection_objs[name] = conn

    @classmethod
    def _get_connection_obj_name(cls, connection):
        # create a unique connection name for connection obj
        # will generate same name if connection has same content
        connection_dict = dict(connection)
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


class FlowBase(AbstractFlowBase, SchemaValidatableMixin):
    def __init__(self, *, data: dict, code: Path, path: Path, **kwargs):
        self._context = FlowContext()
        AbstractFlowBase.__init__(self, data=data, code=code, path=path, **kwargs)
        # hash of flow's entry file, used to skip invoke if entry file is not changed
        self._content_hash = kwargs.pop("content_hash", None)

    @property
    def context(self) -> FlowContext:
        return self._context

    @context.setter
    def context(self, val):
        if not isinstance(val, FlowContext):
            raise UserErrorException("context must be a FlowContext object, got {type(val)} instead.")
        self._context = val

    @property
    def code(self) -> Path:
        """Working directory of the flow."""
        return self._code

    @property
    def path(self) -> Path:
        """Flow file path. Can be script file or flow definition YAML file."""
        return self._path

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


class Flow(FlowBase):
    """A Flow in the context of PromptFlow is a sequence of steps that define a task.
    Each step in the flow could be a prompt that is sent to a language model, or simply a function task,
    and the output of one step can be used as the input to the next.
    Flows can be used to build complex applications with language models.

    Example:

    .. code-block:: python

        from promptflow.entities import Flow
        flow = Flow.load(source="path/to/flow.dag.yaml")
        result = flow(input_a=1, input_b=2)

    """

    def __init__(
        self,
        code: Union[str, PathLike],
        path: Union[str, PathLike],
        dag: dict,
        **kwargs,
    ):
        self.variant = kwargs.pop("variant", None) or {}
        super().__init__(data=dag, code=code, path=path, **kwargs)

    @property
    def environment_variables(self):
        return self._data.get("environment_variables", {})

    @classmethod
    def _load(cls, path: Path, dag: dict, **kwargs):
        return cls(code=path.parent, path=path, dag=dag, **kwargs)

    @classmethod
    def _dispatch_flow_creation(cls, flow_path, raise_error=True, **kwargs):
        """Dispatch flow load to non-dag flow or async flow or prompty."""
        if is_prompty_flow(file_path=flow_path, raise_error=raise_error):
            from .prompty import Prompty

            return Prompty._load(path=flow_path, raise_error=True, **kwargs)

        with open(flow_path, "r", encoding=DEFAULT_ENCODING) as f:
            flow_content = f.read()
            data = load_yaml_string(flow_content)
            content_hash = hash(flow_content)
        if is_flex_flow(yaml_dict=data):
            from .flex import FlexFlow

            return FlexFlow._load(path=flow_path, data=data, raise_error=raise_error, **kwargs)
        else:
            from .dag import Flow

            # TODO: schema validation and warning on unknown fields
            return Flow._load(path=flow_path, dag=data, content_hash=content_hash, **kwargs)

    @classmethod
    def _load_prepare(cls, source: Union[str, PathLike]):
        flow_dir, flow_filename = resolve_flow_path(source)
        flow_path = flow_dir / flow_filename

        if flow_path.suffix not in FLOW_FILE_SUFFIX:
            raise UserErrorException("Source must be a directory or a 'flow.dag.yaml' file or a prompty file")
        return flow_dir, flow_path

    @classmethod
    def load(
        cls,
        source: Union[str, PathLike],
        raise_error=True,
        **kwargs,
    ) -> "Flow":
        """
        Load flow from YAML file.

        :param source: The local yaml source of a flow. Must be a path to a local file.
            If the source is a path, it will be open and read.
            An exception is raised if the file does not exist.
        :type source: Union[PathLike, str]
        :param raise_error: Argument for non-dag flow raise validation error on unknown fields.
        :type raise_error: bool
        :return: A Flow object
        :rtype: Flow
        """
        _, flow_path = cls._load_prepare(source)
        return cls._dispatch_flow_creation(flow_path, raise_error=raise_error, **kwargs)

    def _init_executable(self):
        from promptflow.contracts.flow import Flow as ExecutableFlow

        # for DAG flow, use data to init executable to improve performance
        return ExecutableFlow._from_dict(flow_data=self._data, working_dir=self.code)

    def __eq__(self, other):
        if isinstance(other, Flow):
            return self._content_hash == other._content_hash and self.context == other.context
        return False

    def __hash__(self):
        return hash(self.context) ^ self._content_hash

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
        from promptflow._sdk.entities._flows._flow_context_resolver import FlowContextResolver

        invoker = FlowContextResolver.resolve(flow=self)
        result = invoker._invoke(
            data=inputs,
        )
        return result
