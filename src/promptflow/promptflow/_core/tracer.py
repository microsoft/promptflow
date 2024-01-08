# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import functools
import inspect
import json
import logging
import uuid
from collections.abc import Iterator
from contextvars import ContextVar
from datetime import datetime
from typing import Callable, Optional, Dict

from promptflow._core.generator_proxy import GeneratorProxy, generate_from_proxy
from promptflow._utils.dataclass_serializer import serialize
from promptflow._utils.multimedia_utils import default_json_encoder
from promptflow.contracts.tool import ConnectionType
from promptflow.contracts.trace import Trace, TraceType

from .thread_local_singleton import ThreadLocalSingleton


class Tracer(ThreadLocalSingleton):
    CONTEXT_VAR_NAME = "Tracer"
    context_var = ContextVar(CONTEXT_VAR_NAME, default=None)

    def __init__(self, run_id, node_name: Optional[str] = None):
        self._run_id = run_id
        self._node_name = node_name
        self._traces = []
        self._current_trace_id = ContextVar("current_trace_id", default="")
        self._id_to_trace: Dict[str, Trace] = {}

    @classmethod
    def start_tracing(cls, run_id, node_name: Optional[str] = None):
        current_run_id = cls.current_run_id()
        if current_run_id is not None:
            msg = f"Try to start tracing for run {run_id} but {current_run_id} is already active."
            logging.warning(msg)
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
    def end_tracing(cls, run_id: Optional[str] = None, raise_ex=False):
        tracer = cls.active_instance()
        if not tracer:
            msg = "Try end tracing but no active tracer in current context."
            if raise_ex:
                raise Exception(msg)
            logging.warning(msg)
            return []
        if run_id is not None and tracer._run_id != run_id:
            msg = f"Try to end tracing for run {run_id} but {tracer._run_id} is active."
            logging.warning(msg)
            return []
        tracer._deactivate_in_context()
        return tracer.to_json()

    @classmethod
    def push(cls, trace: Trace):
        obj = cls.active_instance()
        if not obj:
            logging.warning("Try to push trace but no active tracer in current context.")
            return
        obj._push(trace)

    @staticmethod
    def to_serializable(obj):
        if isinstance(obj, dict) and all(isinstance(k, str) for k in obj.keys()):
            return {k: Tracer.to_serializable(v) for k, v in obj.items()}
        if isinstance(obj, GeneratorProxy):
            return obj
        try:
            obj = serialize(obj)
            json.dumps(obj, default=default_json_encoder)
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
        return obj._pop(output, error)

    def _pop(self, output=None, error: Optional[Exception] = None):
        last_trace = self._get_current_trace()
        if not last_trace:
            logging.warning("Try to pop trace but no active trace in current context.")
            return output
        if isinstance(output, Iterator):
            output = GeneratorProxy(output)
        if output is not None:
            last_trace.output = self.to_serializable(output)
        if error is not None:
            last_trace.error = self._format_error(error)
        last_trace.end_time = datetime.utcnow().timestamp()
        self._current_trace_id.set(last_trace.parent_id)

        if isinstance(output, GeneratorProxy):
            return generate_from_proxy(output)
        else:
            return output

    def to_json(self) -> list:
        return serialize(self._traces)

    @staticmethod
    def _format_error(error: Exception) -> dict:
        return {
            "message": str(error),
            "type": type(error).__qualname__,
        }


def _create_trace_from_function_call(f, *, args=[], kwargs={}, trace_type=TraceType.FUNCTION):
    """Initialize a trace object from a function call."""
    sig = inspect.signature(f).parameters

    all_kwargs = {**{k: v for k, v in zip(sig.keys(), args)}, **kwargs}
    all_kwargs = {
        k: ConnectionType.serialize_conn(v) if ConnectionType.is_connection_value(v) else v
        for k, v in all_kwargs.items()
    }
    # TODO: put parameters in self to inputs for builtin tools
    all_kwargs.pop("self", None)

    return Trace(
        name=f.__qualname__,
        type=trace_type,
        start_time=datetime.utcnow().timestamp(),
        inputs=all_kwargs,
        children=[],
    )


def _traced(func: Callable = None, *, trace_type=TraceType.FUNCTION) -> Callable:
    """A wrapper to add trace to a function.

    When a function is wrapped by this wrapper, the function name,
    inputs, outputs, start time, end time, and error (if any) will be recorded.

    It can be used for both sync and async functions.
    For sync functions, it will return a sync function.
    For async functions, it will return an async function.

    :param func: The function to be traced.
    :type func: Callable
    :param trace_type: The type of the trace. Defaults to TraceType.FUNCTION.
    :type trace_type: TraceType, optional
    :return: The wrapped function with trace enabled.
    :rtype: Callable
    """

    def create_trace(func, args, kwargs):
        return _create_trace_from_function_call(func, args=args, kwargs=kwargs, trace_type=trace_type)

    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def wrapped(*args, **kwargs):
            if Tracer.active_instance() is None:
                return await func(*args, **kwargs)  # Do nothing if no tracing is enabled.
            # Should not extract these codes to a separate function here.
            # We directly call func instead of calling Tracer.invoke,
            # because we want to avoid long stack trace when hitting an exception.
            try:
                Tracer.push(create_trace(func, args, kwargs))
                output = await func(*args, **kwargs)
                return Tracer.pop(output)
            except Exception as e:
                Tracer.pop(None, e)
                raise

    else:

        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            if Tracer.active_instance() is None:
                return func(*args, **kwargs)  # Do nothing if no tracing is enabled.
            # Should not extract these codes to a separate function here.
            # We directly call func instead of calling Tracer.invoke,
            # because we want to avoid long stack trace when hitting an exception.
            try:
                Tracer.push(create_trace(func, args, kwargs))
                output = func(*args, **kwargs)
                return Tracer.pop(output)
            except Exception as e:
                Tracer.pop(None, e)
                raise

    wrapped.__original_function = func
    func.__wrapped_function = wrapped

    return wrapped


def trace(func: Callable = None) -> Callable:
    """A decorator to add trace to a function.

    When a function is wrapped by this decorator, the function name,
    inputs, outputs, start time, end time, and error (if any) will be recorded.

    It can be used for both sync and async functions.
    For sync functions, it will return a sync function.
    For async functions, it will return an async function.

    :param func: The function to be traced.
    :type func: Callable
    :return: The wrapped function with trace enabled.
    :rtype: Callable

    :Examples:

    Synchronous function usage:

    .. code-block:: python

        @trace
        def greetings(user_id):
            name = get_name(user_id)
            return f"Hello, {name}"

    Asynchronous function usage:

    .. code-block:: python

        @trace
        async def greetings_async(user_id):
            name = await get_name_async(user_id)
            return f"Hello, {name}"
    """

    return _traced(func, trace_type=TraceType.FUNCTION)
