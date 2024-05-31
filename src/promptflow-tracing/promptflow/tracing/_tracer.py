import inspect
import json
import logging
import uuid
from collections.abc import AsyncIterator, Iterator
from contextvars import ContextVar
from datetime import datetime
from typing import Dict, List, Optional

from ._thread_local_singleton import ThreadLocalSingleton
from ._utils import serialize
from .contracts.iterator_proxy import AsyncIteratorProxy, IteratorProxy
from .contracts.trace import Trace, TraceType


class Tracer(ThreadLocalSingleton):
    CONTEXT_VAR_NAME = "Tracer"
    context_var = ContextVar(CONTEXT_VAR_NAME, default=None)

    def __init__(self, run_id, node_name: Optional[str] = None):
        self._run_id = run_id
        self._node_name = node_name
        self._is_node_span_created = False
        self._traces = []
        self._current_trace_id = ContextVar("current_trace_id", default="")
        self._id_to_trace: Dict[str, Trace] = {}

    @classmethod
    def start_tracing(cls, run_id, node_name: Optional[str] = None):
        from ._utils import is_tracing_disabled

        if is_tracing_disabled():
            return
        current_run_id = cls.current_run_id()
        if current_run_id is not None:
            return
        tracer = cls(run_id, node_name)
        tracer._activate_in_context()

    @classmethod
    def current_run_id(cls):
        tracer = cls.active_instance()
        if not tracer:
            return None
        return tracer._run_id

    @classmethod
    def end_tracing(cls, run_id: Optional[str] = None):
        tracer = cls.active_instance()
        if not tracer:
            return []
        if run_id is not None and tracer._run_id != run_id:
            return []
        tracer._deactivate_in_context()
        return tracer.to_json()

    @classmethod
    def push(cls, trace: Trace):
        obj = cls.active_instance()
        if not obj:
            return
        obj._push(trace)

    @staticmethod
    def to_serializable(obj):
        if isinstance(obj, dict) and all(isinstance(k, str) for k in obj.keys()):
            return {k: Tracer.to_serializable(v) for k, v in obj.items()}
        if isinstance(obj, (IteratorProxy, AsyncIteratorProxy)):
            return obj
        try:
            obj = serialize(obj)
            try:
                from promptflow._utils.utils import default_json_encoder

                json.dumps(obj, default=default_json_encoder)
            except ImportError:
                json.dumps(obj)
        except Exception:
            # We don't want to fail the whole function call because of a serialization error,
            # so we simply convert it to str if it cannot be serialized.
            obj = str(obj)
        return obj

    def _get_current_trace(self):
        trace_id = self._current_trace_id.get()
        if not trace_id:
            return None
        return self._id_to_trace[trace_id]

    def _push(self, trace: Trace):
        if not trace.id:
            trace.id = str(uuid.uuid4())
        if trace.inputs:
            trace.inputs = self.to_serializable(trace.inputs)
        trace.children = []
        if not trace.start_time:
            trace.start_time = datetime.utcnow().timestamp()
        parent_trace = self._get_current_trace()
        if not parent_trace:
            self._traces.append(trace)
            trace.node_name = self._node_name
        else:
            parent_trace.children.append(trace)
            trace.parent_id = parent_trace.id
        self._current_trace_id.set(trace.id)
        self._id_to_trace[trace.id] = trace

    @classmethod
    def pop(cls, output=None, error: Optional[Exception] = None):
        obj = cls.active_instance()
        return obj._pop(output, error) if obj else output

    def _pop(self, output=None, error: Optional[Exception] = None):
        last_trace = self._get_current_trace()
        if not last_trace:
            logging.warning("Try to pop trace but no active trace in current context.")
            return output
        if isinstance(output, Iterator) and not isinstance(output, IteratorProxy):
            output = IteratorProxy(output)
        if isinstance(output, AsyncIterator) and not isinstance(output, AsyncIteratorProxy):
            output = AsyncIteratorProxy(output)
        if output is not None:
            last_trace.output = self.to_serializable(output)
        if error is not None:
            last_trace.error = self._format_error(error)
        last_trace.end_time = datetime.utcnow().timestamp()
        self._current_trace_id.set(last_trace.parent_id)

        return output

    def to_json(self) -> list:
        return serialize(self._traces)

    @staticmethod
    def _format_error(error: Exception) -> dict:
        return {
            "message": str(error),
            "type": type(error).__qualname__,
        }


def _create_trace_from_function_call(
    f,
    *,
    args=None,
    kwargs=None,
    args_to_ignore: Optional[List[str]] = None,
    trace_type=TraceType.FUNCTION,
    name=None,
):
    """
    Creates a trace object from a function call.

    Args:
        f (Callable): The function to be traced.
        args (list, optional): The positional arguments to the function. Defaults to None.
        kwargs (dict, optional): The keyword arguments to the function. Defaults to None.
        args_to_ignore (Optional[List[str]], optional): A list of argument names to be ignored in the trace.
                                                        Defaults to None.
        trace_type (TraceType, optional): The type of the trace. Defaults to TraceType.FUNCTION.
        name (str, optional): The name of the trace. Defaults to None.

    Returns:
        Trace: The created trace object.
    """
    args = args or []
    kwargs = kwargs or {}
    args_to_ignore = set(args_to_ignore or [])
    sig = inspect.signature(f).parameters

    all_kwargs = {**{k: v for k, v in zip(sig.keys(), args)}, **kwargs}
    try:
        # We have removed the dependency of tracing on promptflow, so need to check if the ConnectionType is
        # available before using it.
        from promptflow.contracts.tool import ConnectionType

        all_kwargs = {
            k: ConnectionType.serialize_conn(v) if ConnectionType.is_connection_value(v) else v
            for k, v in all_kwargs.items()
        }
    except ImportError:
        pass

    # TODO: put parameters in self to inputs for builtin tools
    all_kwargs.pop("self", None)
    for key in args_to_ignore:
        all_kwargs.pop(key, None)

    if hasattr(f, "__qualname__"):
        function = f.__qualname__
    else:
        # Get __qualname__ from callable class
        function = f.__call__.__qualname__
    if function.endswith(".__call__"):
        function = function[: -len(".__call__")]
    if trace_type in [TraceType.LLM, TraceType.EMBEDDING] and f.__module__:
        function = f"{f.__module__}.{function}"

    return Trace(
        name=name or function,  # Use the function name as the trace name if not provided
        type=trace_type,
        start_time=datetime.utcnow().timestamp(),
        inputs=all_kwargs,
        children=[],
        function=function,
    )


def get_node_name_from_context(used_for_span_name=False):
    tracer = Tracer.active_instance()
    if tracer is not None:
        if used_for_span_name:
            # Since only the direct children of flow span should have the node name as span name, we need to check if
            # the node span is created, if created, the current span is not a node span, its name should bet set to
            # function name.
            if not tracer._is_node_span_created:
                tracer._is_node_span_created = True
                return tracer._node_name
        else:
            return tracer._node_name
    return None
