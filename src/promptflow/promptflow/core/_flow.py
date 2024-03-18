# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import abc
import json
from os import PathLike
from pathlib import Path
from typing import Optional, Union

from promptflow._constants import DEFAULT_ENCODING
from promptflow._utils.flow_utils import is_flex_flow, resolve_entry_file, resolve_flow_path
from promptflow._utils.yaml_utils import load_yaml_string
from promptflow.core._connection import _Connection
from promptflow.core._utils import generate_flow_meta
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
                    if isinstance(conn, _Connection):  # Core COnnection
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


class FlowBase(abc.ABC):
    def __init__(self, *, data: dict, code: Path, path: Path, **kwargs):
        self._context = FlowContext()
        # flow.dag.yaml's content if provided
        self._data = data
        # working directory of the flow
        self._code = Path(code).resolve()
        # flow file path, can be script file or flow definition YAML file
        self._path = Path(path).resolve()
        # hash of flow's entry file, used to skip invoke if entry file is not changed
        self._content_hash = kwargs.pop("content_hash", None)
        super().__init__(**kwargs)

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

    Simple Example:

    .. code-block:: python

        from promptflow.core import Flow
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

    @classmethod
    def _load(cls, path: Path, dag: dict, **kwargs):
        return cls(code=path.parent, path=path, dag=dag, **kwargs)

    @classmethod
    def _dispatch_flow_creation(cls, is_eager_flow, flow_path, data, content_hash, raise_error=True, **kwargs):
        """Dispatch flow load to non-dag flow or async flow."""
        if is_eager_flow:
            return FlexFlow._load(path=flow_path, data=data, raise_error=raise_error, **kwargs)
        else:
            # TODO: schema validation and warning on unknown fields
            return Flow._load(path=flow_path, dag=data, content_hash=content_hash, **kwargs)

    @classmethod
    def _load_prepare(cls, source: Union[str, PathLike]):
        source_path = Path(source)
        if not source_path.exists():
            raise UserErrorException(f"Source {source_path.absolute().as_posix()} does not exist")

        flow_dir, flow_filename = resolve_flow_path(source_path, new=True)
        flow_path = flow_dir / flow_filename

        if not flow_path.exists():
            raise UserErrorException(f"Flow file {flow_path.absolute().as_posix()} does not exist")

        if flow_path.suffix not in [".yaml", ".yml"]:
            raise UserErrorException("Source must be a directory or a 'flow.dag.yaml' file")
        return source_path, flow_path

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
        with open(flow_path, "r", encoding=DEFAULT_ENCODING) as f:
            flow_content = f.read()
            data = load_yaml_string(flow_content)
            content_hash = hash(flow_content)
        return cls._dispatch_flow_creation(
            is_flex_flow(yaml_dict=data), flow_path, data, content_hash, raise_error=raise_error, **kwargs
        )

    def _init_executable(self):
        from promptflow.contracts.flow import Flow as ExecutableFlow

        # for DAG flow, use data to init executable to improve performance
        return ExecutableFlow._from_dict(flow_dag=self._data, working_dir=self.code)

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
        from promptflow.core._flow_context_resolver import FlowContextResolver

        invoker = FlowContextResolver.resolve(flow=self)
        result = invoker._invoke(
            data=inputs,
        )
        return result


class FlexFlow(Flow):
    """A FlexFlow represents an non-dag flow, which uses codes to define the flow.
    FlexFlow basically behave like a Flow, but its entry function should be provided in the flow.dag.yaml file.
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

    @classmethod
    def _load(cls, path: Path, data: dict, **kwargs):
        entry = data.get("entry")
        code = path.parent

        if entry is None:
            raise UserErrorException(f"Entry function is not specified for flow {path}")
        return cls(path=path, code=code, entry=entry, data=data, **kwargs)

    # region overrides
    @classmethod
    def load(
        cls,
        source: Union[str, PathLike],
        raise_error=True,
        **kwargs,
    ) -> "FlexFlow":
        """
        Direct load non-dag flow from YAML file.

        :param source: The local yaml source of a flow. Must be a path to a local file.
            If the source is a path, it will be open and read.
            An exception is raised if the file does not exist.
        :type source: Union[PathLike, str]
        :param raise_error: Argument for non-dag flow raise validation error on unknown fields.
        :type raise_error: bool
        :return: A EagerFlow object
        :rtype: EagerFlow
        """
        _, flow_path = cls._load_prepare(source)
        with open(flow_path, "r", encoding=DEFAULT_ENCODING) as f:
            flow_content = f.read()
            data = load_yaml_string(flow_content)
        if not is_flex_flow(yaml_dict=data):
            raise UserErrorException("Please load an non-dag flow with EagerFlow.load method.")
        return cls._load(path=flow_path, data=data, **kwargs)

    def _init_executable(self):
        from promptflow.contracts.flow import EagerFlow as ExecutableEagerFlow

        meta_dict = generate_flow_meta(
            flow_directory=self.code,
            source_path=self.entry_file,
            data=self._data,
            dump=False,
        )
        return ExecutableEagerFlow.deserialize(meta_dict)

    def __call__(self, *args, **kwargs):
        """Direct call of non-dag flow WILL cause exceptions."""
        raise UserErrorException("FlexFlow can not be called as a function.")

    # endregion

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


class AsyncFlow(Flow):
    """Async flow is based on Flow, which is used to invoke flow in async mode.

    Simple Example:

    .. code-block:: python

        from promptflow.core import class AsyncFlow
        flow = AsyncFlow.load(source="path/to/flow.dag.yaml")
        result = await flow(input_a=1, input_b=2)

    """

    # region overrides
    @classmethod
    def load(
        cls,
        source: Union[str, PathLike],
        raise_error=True,
        **kwargs,
    ) -> "AsyncFlow":
        """
        Direct load flow from YAML file.

        :param source: The local yaml source of a flow. Must be a path to a local file.
            If the source is a path, it will be open and read.
            An exception is raised if the file does not exist.
        :type source: Union[PathLike, str]
        :param raise_error: Argument for non-dag flow raise validation error on unknown fields.
        :type raise_error: bool
        :return: An AsyncFlow object
        :rtype: AsyncFlow
        """
        _, flow_path = cls._load_prepare(source)
        with open(flow_path, "r", encoding=DEFAULT_ENCODING) as f:
            flow_content = f.read()
            data = load_yaml_string(flow_content)
            content_hash = hash(flow_content)
        return cls._load(path=flow_path, dag=data, content_hash=content_hash, **kwargs)

    # endregion

    async def __call__(self, *args, **kwargs):
        """Calling flow as a function in async, the inputs should be provided with key word arguments.
        Returns the output of the flow.
        The function call throws UserErrorException: if the flow is not valid or the inputs are not valid.
        SystemErrorException: if the flow execution failed due to unexpected executor error.

        :param args: positional arguments are not supported.
        :param kwargs: flow inputs with key word arguments.
        :return:
        """
        if args:
            raise UserErrorException("Flow can only be called with keyword arguments.")

        result = await self.invoke_async(inputs=kwargs)
        return result.output

    async def invoke_async(self, inputs: dict) -> "LineResult":
        """Invoke a flow and get a LineResult object."""
        from promptflow.core._flow_context_resolver import FlowContextResolver

        invoker = FlowContextResolver.resolve_async_invoker(flow=self)
        result = await invoker._invoke_async(
            data=inputs,
        )
        return result
