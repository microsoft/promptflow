# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import docutils.nodes
import functools
import threading
import time
from docutils.core import publish_doctree
from contextvars import ContextVar
from functools import partial
from logging import WARNING
from typing import Callable, List, Optional

from promptflow._core._errors import ToolExecutionError
# from promptflow._core.thread_local_singleton import ThreadLocalSingleton
from promptflow._core.tracer import Tracer
from promptflow._utils.logger_utils import logger
from promptflow._utils.thread_utils import RepeatLogTimer
from promptflow._utils.utils import generate_elapsed_time_messages
from promptflow.contracts.flow import InputAssignment, Node, ToolSource
from promptflow.executor._tool_resolver import ToolResolver
from promptflow.exceptions import PromptflowException


class DefaultToolInvoker():
    CONTEXT_VAR_NAME = "Invoker"
    context_var = ContextVar(CONTEXT_VAR_NAME, default=None)

    def __init__(self):
        self._tools = {}
        self._assistant_tools = {}

    @property
    def tools(self):
        return self._tools

    # @classmethod
    # def start_invoker(cls):
    #     invoker = cls()
    #     active_invoker = cls.active_instance()
    #     if active_invoker:
    #         active_invoker._deactivate_in_context()
    #     cls._activate_in_context(invoker)
    #     return invoker

    @classmethod
    def load_tools(self, nodes: List[Node]):
        invoker = DefaultToolInvoker()
        tool_resolver = ToolResolver.active_instance()
        invoker._tools = {node.name: tool_resolver.resolve_tool_by_node(node) for node in nodes}
        return invoker

    @classmethod
    def load_assistant_tools(cls, tools: list):
        invoker = DefaultToolInvoker()
        tool_resolver = ToolResolver.active_instance()
        for tool in tools:
            if tool["type"] != "promptflow_tool":
                continue
            inputs = tool.get("pre_assigned_inputs", {})
            updated_inputs = {}
            for input_name, value in inputs.items():
                updated_inputs[input_name] = InputAssignment.deserialize(value)
            node = Node(
                name="assistant_node",
                tool="assistant_tool",
                inputs=updated_inputs,
                source=ToolSource.deserialize(tool["source"])
            )
            resolved_tool = tool_resolver._resolve_script_node(node, convert_input_types=True)
            if resolved_tool.node.inputs:
                inputs = {name: value.value for name, value in resolved_tool.node.inputs.items()}
                callable = partial(resolved_tool.callable, **inputs)
                resolved_tool.callable = callable
            invoker._assistant_tools[resolved_tool.definition.function] = resolved_tool
        return invoker

    def invoke_assistant_tool(self, func_name, kwargs):
        return self._assistant_tools[func_name].callable(**kwargs)

    def to_openai_tools(self):
        openai_tools = []
        for name, tool in self._assistant_tools.items():
            preset_inputs = [name for name, _ in tool.node.inputs.items()]
            description = self._get_openai_tool_description(name, tool.definition.description, preset_inputs)
            openai_tools.append(description)
        return openai_tools

    def _get_openai_tool_description(self, func_name: str, docstring: str, preset_inputs: Optional[list] = None):
        to_openai_type = {"str": "string", "int": "number"}

        doctree = publish_doctree(docstring)
        params = {}

        for field in doctree.traverse(docutils.nodes.field):
            field_name = field[0].astext()
            field_body = field[1].astext()

            if field_name.startswith("param"):
                param_name = field_name.split(' ')[1]
                if param_name in preset_inputs:
                    continue
                if param_name not in params:
                    params[param_name] = {}
                params[param_name]["description"] = field_body
            if field_name.startswith("type"):
                param_name = field_name.split(' ')[1]
                if param_name in preset_inputs:
                    continue
                if param_name not in params:
                    params[param_name] = {}
                params[param_name]["type"] = to_openai_type[field_body] if field_body in to_openai_type else field_body

        return {
            "type": "function",
            "function": {
                "name": func_name,
                "description": doctree[0].astext(),
                "parameters": {
                    "type": "object",
                    "properties": params,
                    "required": list(params.keys())
                }
            }
        }

    def invoke_tool(self, node: Node, f: Callable, run_id: str, line_number, kwargs):
        Tracer.start_tracing(run_id, node.name)
        result = self._invoke_tool_with_timer(node, f, line_number, kwargs)
        traces = Tracer.end_tracing(run_id)
        return result, traces

    async def invoke_tool_async(self, node: Node, f: Callable, run_id: str, kwargs):
        Tracer.start_tracing(run_id, node.name)
        result = await self._invoke_tool_async_inner(node, f, kwargs)
        traces = Tracer.end_tracing(run_id)
        return result, traces

    async def _invoke_tool_async_inner(self, node: Node, f: Callable, kwargs):
        module = f.func.__module__ if isinstance(f, functools.partial) else f.__module__
        try:
            return await f(**kwargs)
        except PromptflowException as e:
            # All the exceptions from built-in tools are PromptflowException.
            # For these cases, raise the exception directly.
            if module is not None:
                e.module = module
            raise e
        except Exception as e:
            # Otherwise, we assume the error comes from user's tool.
            # For these cases, raise ToolExecutionError, which is classified as UserError
            # and shows stack trace in the error message to make it easy for user to troubleshoot.
            raise ToolExecutionError(node_name=node.name, module=module) from e

    def _invoke_tool_with_timer(self, node: Node, f: Callable, line_number, kwargs):
        module = f.func.__module__ if isinstance(f, functools.partial) else f.__module__
        node_name = node.name
        try:
            logging_name = node_name
            if line_number is not None:
                logging_name = f"{node_name} in line {line_number}"
            interval_seconds = 60
            start_time = time.perf_counter()
            thread_id = threading.current_thread().ident
            with RepeatLogTimer(
                interval_seconds=interval_seconds,
                logger=logger,
                level=WARNING,
                log_message_function=generate_elapsed_time_messages,
                args=(logging_name, start_time, interval_seconds, thread_id),
            ):
                return f(**kwargs)
        except PromptflowException as e:
            # All the exceptions from built-in tools are PromptflowException.
            # For these cases, raise the exception directly.
            if module is not None:
                e.module = module
            raise e
        except Exception as e:
            # Otherwise, we assume the error comes from user's tool.
            # For these cases, raise ToolExecutionError, which is classified as UserError
            # and shows stack trace in the error message to make it easy for user to troubleshoot.
            raise ToolExecutionError(node_name=node_name, module=module) from e
