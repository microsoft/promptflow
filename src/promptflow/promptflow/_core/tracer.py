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
from importlib.metadata import version
from threading import Lock
from typing import Callable, Dict, List, Optional

import opentelemetry.trace as otel_trace
from opentelemetry.trace import Link
from opentelemetry.trace.status import StatusCode
from opentelemetry.trace.span import NonRecordingSpan
from opentelemetry.sdk.trace import ReadableSpan

from promptflow._core.generator_proxy import GeneratorProxy, generate_from_proxy
from promptflow._core.operation_context import OperationContext
from promptflow._utils.dataclass_serializer import serialize
from promptflow._utils.openai_metrics_calculator import OpenAIMetricsCalculator
from promptflow._utils.tool_utils import get_inputs_for_prompt_template, get_prompt_param_name_from_func
from promptflow.contracts.tool import ConnectionType
from promptflow.contracts.trace import Trace, TraceType

from .._utils.utils import default_json_encoder
from .thread_local_singleton import ThreadLocalSingleton


IS_LEGACY_OPENAI = version("openai").startswith("0.")


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


class TokenCollector:
    _lock = Lock()

    def __init__(self):
        self._span_id_to_tokens = {}

    def collect_openai_tokens(self, span, output):
        span_id = span.get_span_context().span_id
        if not inspect.isgenerator(output) and hasattr(output, "usage") and output.usage is not None:
            tokens = output.usage.dict()
            if tokens:
                with self._lock:
                    self._span_id_to_tokens[span_id] = tokens

    def collect_openai_tokens_for_streaming(self, span, inputs, output, is_chat):
        span_id = span.get_span_context().span_id
        calculator = OpenAIMetricsCalculator()
        if is_chat:
            tokens = calculator.get_openai_metrics_for_chat_api(inputs, output)
        else:
            tokens = calculator.get_openai_metrics_for_completion_api(inputs, output)
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
    if trace_type in [TraceType.LLM, TraceType.EMBEDDING] and f.__module__:
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


def enrich_span_with_prompt_info(span, func, kwargs):
    try:
        # Assume there is only one prompt template parameter in the function,
        # we use the first one by default if there are multiple.
        prompt_tpl_param_name = get_prompt_param_name_from_func(func)
        if prompt_tpl_param_name is not None:
            prompt_tpl = kwargs.get(prompt_tpl_param_name)
            prompt_vars = {key: kwargs.get(key) for key in get_inputs_for_prompt_template(prompt_tpl) if key in kwargs}
            prompt_info = {"prompt.template": prompt_tpl, "prompt.variables": serialize_attribute(prompt_vars)}
            span.set_attributes(prompt_info)
    except Exception as e:
        logging.warning(f"Failed to enrich span with prompt info: {e}")


def enrich_span_with_input(span, input):
    try:
        serialized_input = serialize_attribute(input)
        span.set_attribute("inputs", serialized_input)
    except Exception as e:
        logging.warning(f"Failed to enrich span with input: {e}")

    return input


def enrich_span_with_trace_type(span, inputs, output, trace_type):
    if trace_type == TraceType.LLM:
        # Handle the non-streaming output of LLM, the streaming output will be handled in traced_generator.
        token_collector.collect_openai_tokens(span, output)
        enrich_span_with_llm(span, output)
    elif trace_type == TraceType.EMBEDDING:
        token_collector.collect_openai_tokens(span, output)
        enrich_span_with_embedding(span, inputs, output)
    enrich_span_with_openai_tokens(span, trace_type)
    enrich_span_with_output(span, output)
    # If the output is a generator, while the span is a valid span, we will trace the generator.
    if isinstance(output, Iterator) and not isinstance(span, NonRecordingSpan):
        output = traced_generator(span, inputs, output)
    return output


def traced_generator(original_span: ReadableSpan, inputs, generator):
    context = original_span.get_span_context()
    link = Link(context)
    # If start_trace is not called, the name of the original_span will be empty.
    with open_telemetry_tracer.start_as_current_span(
        f"Iterated({original_span.name})",
        links=[link],
    ) as span:
        span.set_attributes(original_span.attributes)
        generator_proxy = GeneratorProxy(generator)
        yield from generator_proxy
        generator_output = generator_proxy.items

        # Enrich LLM span for OpenAI steaming message and token count
        if original_span.attributes["span_type"] == "LLM" and not IS_LEGACY_OPENAI:
            from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
            from openai.types.completion import Completion

            chunks = []
            role = "assistant"
            is_chat = False
            model = None
            for item in generator_output:
                if not model and hasattr(item, "model"):
                    model = item.model
                if isinstance(item, ChatCompletionChunk):
                    is_chat = True
                    if item.choices and item.choices[0].delta.content:
                        chunks.append(item.choices[0].delta.content)
                        role = item.choices[0].delta.role or role
                elif isinstance(item, Completion):
                    if item.choices and item.choices[0].text:
                        chunks.append(item.choices[0].text)
            if chunks:
                text = "".join(chunks)
                message = {"content": text, "role": role} if is_chat else text
                span.set_attribute("llm.generated_message", serialize_attribute(message))
            span.set_attribute("llm.model", model)
            token_collector.collect_openai_tokens_for_streaming(span, inputs, generator_output, is_chat)
        enrich_span_with_openai_tokens(span, TraceType(original_span.attributes["span_type"]))
        span.set_attribute("output", serialize_attribute(generator_output))
        span.set_status(StatusCode.OK)
    token_collector.collect_openai_tokens_for_parent_span(span)


def enrich_span_with_output(span, output):
    try:
        serialized_output = serialize_attribute(output)
        span.set_attribute("output", serialized_output)
    except Exception as e:
        logging.warning(f"Failed to enrich span with output: {e}")


def enrich_span_with_openai_tokens(span, trace_type):
    try:
        tokens = token_collector.try_get_openai_tokens(span.get_span_context().span_id)
        if tokens:
            span_tokens = {f"__computed__.cumulative_token_count.{k.split('_')[0]}": v for k, v in tokens.items()}
            if trace_type in [TraceType.LLM, TraceType.EMBEDDING]:
                llm_tokens = {f"{trace_type.value.lower()}.token_count.{k.split('_')[0]}": v for k, v in tokens.items()}
                span_tokens.update(llm_tokens)
            span.set_attributes(span_tokens)
    except Exception as e:
        logging.warning(f"Failed to enrich span with openai tokens: {e}")


def enrich_span_with_embedding(span, inputs, output):
    from openai.types.create_embedding_response import CreateEmbeddingResponse

    try:
        if isinstance(output, CreateEmbeddingResponse):
            span.set_attribute("embedding.model", output.model)
            embeddings = []
            input_list = [emb_input] if _is_single_input(emb_input := inputs["input"]) else emb_input
            for emb in output.data:
                emb_text = i if isinstance(i := input_list[emb.index], str) else f"<{len(i)} dimensional token>"
                embeddings.append(
                    {
                        "embedding.vector": f"<{len(emb.embedding)} dimensional vector>",
                        "embedding.text": emb_text,
                    }
                )
            span.set_attribute("embedding.embeddings", serialize_attribute(embeddings))
    except Exception as e:
        logging.warning(f"Failed to enrich span with embedding: {e}")


def _is_single_input(embedding_inputs):
    # OpenAI Embedding API accepts a single string/tokenized string or a list of string/tokenized string as input.
    # For the single string/tokenized string case, we should return true, otherwise return false.
    if (isinstance(embedding_inputs, str)):
        # input is a string
        return True
    elif (isinstance(embedding_inputs, list) and all(isinstance(i, int) for i in embedding_inputs)):
        # input is a token array
        return True
    return False


def enrich_span_with_llm(span, output):
    try:
        if not IS_LEGACY_OPENAI:
            from openai.types.chat.chat_completion import ChatCompletion
            from openai.types.completion import Completion

            # Enrich LLM span for OpenAI model
            if isinstance(output, (ChatCompletion, Completion)):
                span.set_attribute("llm.model", output.model)

            # Enrich LLM span for OpenAI generated message
            if isinstance(output, ChatCompletion):
                span.set_attribute("llm.generated_message", output.choices[0].message)
            elif isinstance(output, Completion):
                span.set_attribute("llm.generated_message", output.choices[0].text)
    except Exception as e:
        logging.warning(f"Failed to enrich span with llm model: {e}")


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
        # Fall back to trace.name if we can't get node name for better view.
        span_name = get_node_name_from_context() or trace.name if trace_type == TraceType.TOOL else trace.name
        with open_telemetry_tracer.start_as_current_span(span_name) as span:
            enrich_span_with_trace(span, trace)
            enrich_span_with_prompt_info(span, func, kwargs)

            # Should not extract these codes to a separate function here.
            # We directly call func instead of calling Tracer.invoke,
            # because we want to avoid long stack trace when hitting an exception.
            try:
                Tracer.push(trace)
                enrich_span_with_input(span, trace.inputs)
                output = await func(*args, **kwargs)
                output = enrich_span_with_trace_type(span, trace.inputs, output, trace_type)
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
        # Fall back to trace.name if we can't get node name for better view.
        span_name = get_node_name_from_context() or trace.name if trace_type == TraceType.TOOL else trace.name
        with open_telemetry_tracer.start_as_current_span(span_name) as span:
            enrich_span_with_trace(span, trace)
            enrich_span_with_prompt_info(span, func, kwargs)

            # Should not extract these codes to a separate function here.
            # We directly call func instead of calling Tracer.invoke,
            # because we want to avoid long stack trace when hitting an exception.
            try:
                Tracer.push(trace)
                enrich_span_with_input(span, trace.inputs)
                output = func(*args, **kwargs)
                output = enrich_span_with_trace_type(span, trace.inputs, output, trace_type)
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
