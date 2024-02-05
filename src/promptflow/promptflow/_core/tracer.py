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
from threading import Lock
from typing import Callable, Dict, List, Optional

import opentelemetry.trace as otel_trace
from opentelemetry.trace.status import StatusCode

from promptflow._core.generator_proxy import GeneratorProxy, generate_from_proxy
from promptflow._core.operation_context import OperationContext
from promptflow._utils.dataclass_serializer import serialize
from promptflow._utils.multimedia_utils import default_json_encoder
from promptflow.contracts.tool import ConnectionType
from promptflow.contracts.trace import Trace, TraceType

from .thread_local_singleton import ThreadLocalSingleton


open_telemetry_tracer = otel_trace.get_tracer("promptflow")


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
        return obj._pop(output, error) if obj else output

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


class TokenCollector():
    _lock = Lock()

    def __init__(self):
        self._span_id_to_tokens = {}

    def collect_openai_tokens(self, span, output):
        span_id = span.get_span_context().span_id
        if not inspect.isgenerator(output) and hasattr(output, "usage") and output.usage is not None:
            tokens = {
                f"__computed__.cumulative_token_count.{k.split('_')[0]}": v for k, v in output.usage.dict().items()
            }
            if tokens:
                with self._lock:
                    self._span_id_to_tokens[span_id] = tokens

    def collect_openai_tokens_for_parent_span(self, span):
        tokens = self.try_get_openai_tokens(span.get_span_context().span_id)
        if tokens:
            if not hasattr(span, "parent") or span.parent is None:
                return
            parent_span_id = span.parent.span_id
            with self._lock:
                if parent_span_id in self._span_id_to_tokens:
                    merged_tokens = {
                        key: self._span_id_to_tokens[parent_span_id].get(key, 0) + tokens.get(key, 0)
                        for key in set(self._span_id_to_tokens[parent_span_id]) | set(tokens)
                    }
                    self._span_id_to_tokens[parent_span_id] = merged_tokens
                else:
                    self._span_id_to_tokens[parent_span_id] = tokens

    def try_get_openai_tokens(self, span_id):
        with self._lock:
            return self._span_id_to_tokens.get(span_id, None)


token_collector = TokenCollector()


def _create_trace_from_function_call(
    f, *, args=None, kwargs=None, args_to_ignore: Optional[List[str]] = None, trace_type=TraceType.FUNCTION
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

    Returns:
        Trace: The created trace object.
    """
    args = args or []
    kwargs = kwargs or {}
    args_to_ignore = set(args_to_ignore or [])
    sig = inspect.signature(f).parameters

    all_kwargs = {**{k: v for k, v in zip(sig.keys(), args)}, **kwargs}
    all_kwargs = {
        k: ConnectionType.serialize_conn(v) if ConnectionType.is_connection_value(v) else v
        for k, v in all_kwargs.items()
    }
    # TODO: put parameters in self to inputs for builtin tools
    all_kwargs.pop("self", None)
    for key in args_to_ignore:
        all_kwargs.pop(key, None)

    name = f.__qualname__
    if trace_type == TraceType.LLM and f.__module__:
        name = f"{f.__module__}.{name}"

    return Trace(
        name=name,
        type=trace_type,
        start_time=datetime.utcnow().timestamp(),
        inputs=all_kwargs,
        children=[],
    )


def get_node_name_from_context():
    tracer = Tracer.active_instance()
    if tracer is not None:
        return tracer._node_name
    return None


def enrich_span_with_context(span):
    try:
        attrs_from_context = OperationContext.get_instance()._get_otel_attributes()
        span.set_attributes(attrs_from_context)
    except Exception as e:
        logging.warning(f"Failed to enrich span with context: {e}")


def enrich_span_with_trace(span, trace):
    try:
        span.set_attributes(
            {
                "framework": "promptflow",
                "span_type": trace.type.value,
                "function": trace.name,
            }
        )
        node_name = get_node_name_from_context()
        if node_name:
            span.set_attribute("node_name", node_name)
        enrich_span_with_context(span)
    except Exception as e:
        logging.warning(f"Failed to enrich span with trace: {e}")


def enrich_span_with_input(span, input):
    try:
        serialized_input = serialize_attribute(input)
        span.set_attribute("inputs", serialized_input)
    except Exception as e:
        logging.warning(f"Failed to enrich span with input: {e}")

    return input


def enrich_span_with_output(span, output):
    try:
        serialized_output = serialize_attribute(output)
        span.set_attribute("output", serialized_output)
        tokens = token_collector.try_get_openai_tokens(span.get_span_context().span_id)
        if tokens:
            span.set_attributes(tokens)
    except Exception as e:
        logging.warning(f"Failed to enrich span with output: {e}")

    return output


def serialize_attribute(value):
    """Serialize values that can be used as attributes in span."""
    try:
        serializable = Tracer.to_serializable(value)
        serialized_value = serialize(serializable)
        return json.dumps(serialized_value, indent=2, default=default_json_encoder)
    except Exception as e:
        logging.warning(f"Failed to serialize attribute: {e}")
        return None


def _traced(
    func: Callable = None, *, args_to_ignore: Optional[List[str]] = None, trace_type=TraceType.FUNCTION
) -> Callable:
    """
    Decorator that adds tracing to a function.

    Args:
        func (Callable): The function to be traced.
        args_to_ignore (Optional[List[str]], optional): A list of argument names to be ignored in the trace.
                                                        Defaults to None.
        trace_type (TraceType, optional): The type of the trace. Defaults to TraceType.FUNCTION.

    Returns:
        Callable: The traced function.
    """
    wrapped_method = _traced_async if inspect.iscoroutinefunction(func) else _traced_sync
    return wrapped_method(func, args_to_ignore=args_to_ignore, trace_type=trace_type)


def _traced_async(
    func: Callable = None, *, args_to_ignore: Optional[List[str]] = None, trace_type=TraceType.FUNCTION
) -> Callable:
    """
    Decorator that adds tracing to an asynchronous function.

    Args:
        func (Callable): The function to be traced.
        args_to_ignore (Optional[List[str]], optional): A list of argument names to be ignored in the trace.
                                                        Defaults to None.
        trace_type (TraceType, optional): The type of the trace. Defaults to TraceType.FUNCTION.

    Returns:
        Callable: The traced function.
    """

    def create_trace(func, args, kwargs):
        return _create_trace_from_function_call(
            func, args=args, kwargs=kwargs, args_to_ignore=args_to_ignore, trace_type=trace_type
        )

    @functools.wraps(func)
    async def wrapped(*args, **kwargs):
        trace = create_trace(func, args, kwargs)
        span_name = get_node_name_from_context() if trace_type == TraceType.TOOL else trace.name
        with open_telemetry_tracer.start_as_current_span(span_name) as span:
            enrich_span_with_trace(span, trace)

            # Should not extract these codes to a separate function here.
            # We directly call func instead of calling Tracer.invoke,
            # because we want to avoid long stack trace when hitting an exception.
            try:
                Tracer.push(trace)
                enrich_span_with_input(span, trace.inputs)
                output = await func(*args, **kwargs)
                if trace_type == TraceType.LLM:
                    token_collector.collect_openai_tokens(span, output)
                enrich_span_with_output(span, output)
                span.set_status(StatusCode.OK)
                output = Tracer.pop(output)
            except Exception as e:
                Tracer.pop(None, e)
                raise
        token_collector.collect_openai_tokens_for_parent_span(span)
        return output

    wrapped.__original_function = func

    return wrapped


def _traced_sync(func: Callable = None, *, args_to_ignore=None, trace_type=TraceType.FUNCTION) -> Callable:
    """
    Decorator that adds tracing to a synchronous function.

    Args:
        func (Callable): The function to be traced.
        args_to_ignore (Optional[List[str]], optional): A list of argument names to be ignored in the trace.
                                                        Defaults to None.
        trace_type (TraceType, optional): The type of the trace. Defaults to TraceType.FUNCTION.

    Returns:
        Callable: The traced function.
    """

    def create_trace(func, args, kwargs):
        return _create_trace_from_function_call(
            func, args=args, kwargs=kwargs, args_to_ignore=args_to_ignore, trace_type=trace_type
        )

    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        trace = create_trace(func, args, kwargs)
        span_name = get_node_name_from_context() if trace_type == TraceType.TOOL else trace.name
        with open_telemetry_tracer.start_as_current_span(span_name) as span:
            enrich_span_with_trace(span, trace)

            # Should not extract these codes to a separate function here.
            # We directly call func instead of calling Tracer.invoke,
            # because we want to avoid long stack trace when hitting an exception.
            try:
                Tracer.push(trace)
                enrich_span_with_input(span, trace.inputs)
                output = func(*args, **kwargs)
                if trace_type == TraceType.LLM:
                    token_collector.collect_openai_tokens(span, output)
                enrich_span_with_output(span, output)
                span.set_status(StatusCode.OK)
                output = Tracer.pop(output)
            except Exception as e:
                Tracer.pop(None, e)
                raise
        token_collector.collect_openai_tokens_for_parent_span(span)
        return output

    wrapped.__original_function = func

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
