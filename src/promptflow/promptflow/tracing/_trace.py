# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import functools
import inspect
import json
import logging
from collections.abc import Iterator
from importlib.metadata import version
from threading import Lock
from typing import Callable, List, Optional

import opentelemetry.trace as otel_trace
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.trace import Link
from opentelemetry.trace.span import NonRecordingSpan
from opentelemetry.trace.status import StatusCode

from ._operation_context import OperationContext
from ._tracer import Tracer, _create_trace_from_function_call, get_node_name_from_context
from ._utils import get_input_names_for_prompt_template, get_prompt_param_name_from_func, serialize
from .contracts.generator_proxy import GeneratorProxy
from .contracts.trace import TraceType

IS_LEGACY_OPENAI = version("openai").startswith("0.")

open_telemetry_tracer = otel_trace.get_tracer("promptflow")


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
            prompt_vars = {
                name: kwargs.get(name) for name in get_input_names_for_prompt_template(prompt_tpl) if name in kwargs
            }
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
        token_collector.collect_openai_tokens(span, output)
        enrich_span_with_llm_model(span, output)
    elif trace_type == TraceType.EMBEDDING:
        token_collector.collect_openai_tokens(span, output)
        enrich_span_with_embedding(span, inputs, output)
    enrich_span_with_openai_tokens(span, trace_type)
    return enrich_span_with_output(span, output)


def traced_generator(generator, original_span: ReadableSpan):
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

        # Enrich LLM span for openai steaming message
        # TODO: Enrich LLM token count for streaming scenario
        if original_span.attributes["span_type"] == "LLM" and not IS_LEGACY_OPENAI:
            from openai.types.chat.chat_completion_chunk import ChatCompletionChunk

            chunks = []
            role = "assistant"
            for item in generator_output:
                if not isinstance(item, ChatCompletionChunk):
                    continue
                if item.choices and item.choices[0].delta.content:
                    chunks.append(item.choices[0].delta.content)
                    role = item.choices[0].delta.role or role
            if chunks:
                text = "".join(chunks)
                message = {"content": text, "role": role}
                span.set_attribute("llm.generated_message", serialize_attribute(message))
        serialized_output = serialize_attribute(generator_output)
        span.set_attribute("output", serialized_output)


def enrich_span_with_output(span, output):
    try:
        serialized_output = serialize_attribute(output)
        span.set_attribute("output", serialized_output)
        # If the output is a generator, while the span is a valid span, we will trace the generator.
        if isinstance(output, Iterator) and not isinstance(span, NonRecordingSpan):
            output = traced_generator(output, span)
    except Exception as e:
        logging.warning(f"Failed to enrich span with output: {e}")

    return output


def enrich_span_with_openai_tokens(span, trace_type):
    try:
        tokens = token_collector.try_get_openai_tokens(span.get_span_context().span_id)
        if tokens:
            span_tokens = {f"__computed__.cumulative_token_count.{k.split('_')[0]}": v for k, v in tokens.items()}
            if trace_type in [TraceType.LLM, TraceType.EMBEDDING]:
                llm_tokens = {f"llm.usage.{k}": v for k, v in tokens.items()}
                span_tokens.update(llm_tokens)
            span.set_attributes(span_tokens)
    except Exception as e:
        logging.warning(f"Failed to enrich span with openai tokens: {e}")


def enrich_span_with_embedding(span, inputs, output):
    from openai.types.create_embedding_response import CreateEmbeddingResponse

    try:
        if isinstance(output, CreateEmbeddingResponse):
            span.set_attribute("llm.response.model", output.model)
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
    if isinstance(embedding_inputs, str):
        # input is a string
        return True
    elif isinstance(embedding_inputs, list) and all(isinstance(i, int) for i in embedding_inputs):
        # input is a token array
        return True
    return False


def enrich_span_with_llm_model(span, output):
    try:
        if not IS_LEGACY_OPENAI:
            from openai.types.chat.chat_completion import ChatCompletion
            from openai.types.completion import Completion

            if isinstance(output, (ChatCompletion, Completion)):
                span.set_attribute("llm.response.model", output.model)
    except Exception as e:
        logging.warning(f"Failed to enrich span with llm model: {e}")


def serialize_attribute(value):
    """Serialize values that can be used as attributes in span."""
    try:
        serializable = Tracer.to_serializable(value)
        serialized_value = serialize(serializable)
        try:
            from promptflow._utils.utils import default_json_encoder

            return json.dumps(serialized_value, indent=2, default=default_json_encoder)
        except ImportError:
            return json.dumps(serialized_value, indent=2)
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
        # For node span we set the span name to node name, otherwise we use the function name.
        span_name = get_node_name_from_context(used_for_span_name=True) or trace.name
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
        # For node span we set the span name to node name, otherwise we use the function name.
        span_name = get_node_name_from_context(used_for_span_name=True) or trace.name
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
