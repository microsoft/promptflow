# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import logging
import threading
import time
import uuid
from contextvars import ContextVar
from logging import WARNING
from typing import Callable, List

from promptflow._core._errors import ToolExecutionError
from promptflow._core.cache_manager import AbstractCacheManager, CacheInfo, CacheResult
from promptflow._core.operation_context import OperationContext
from promptflow._core.tool import parse_all_args
from promptflow._utils.logger_utils import flow_logger, logger
from promptflow._utils.thread_utils import RepeatLogTimer
from promptflow._utils.utils import generate_elapsed_time_messages
from promptflow.contracts.flow import Node
from promptflow.contracts.run_info import RunInfo
from promptflow.exceptions import PromptflowException

from .openai_injector import Tracer
from .run_tracker import RunTracker
from .thread_local_singleton import ThreadLocalSingleton


class FlowExecutionContext(ThreadLocalSingleton):
    """The context for a flow execution."""

    CONTEXT_VAR_NAME = "Flow"
    context_var = ContextVar(CONTEXT_VAR_NAME, default=None)

    def __init__(
        self,
        name,
        run_tracker: RunTracker,
        cache_manager: AbstractCacheManager,
        run_id=None,
        flow_id=None,
        line_number=None,
        variant_id=None,
    ):
        self._name = name
        self._current_tool = None
        self._run_tracker = run_tracker
        self._cache_manager = cache_manager
        self._run_id = run_id or str(uuid.uuid4())
        self._flow_id = flow_id or self._run_id
        self._line_number = line_number
        self._variant_id = variant_id
        #  TODO: use context var qu save the current node to enable multi-threading
        self._current_node: Node = None

    def copy(self):
        return FlowExecutionContext(
            name=self._name,
            run_tracker=self._run_tracker,
            cache_manager=self._cache_manager,
            run_id=self._run_id,
            flow_id=self._flow_id,
            line_number=self._line_number,
            variant_id=self._variant_id,
        )

    def update_operation_context(self):
        flow_context_info = {"flow-id": self._flow_id, "root-run-id": self._run_id}
        OperationContext.get_instance().update(flow_context_info)

    @property
    def current_node(self) -> Node:
        return self._current_node

    @current_node.setter
    def current_node(self, node: Node):
        self._current_node = node
        self._batch_state = False

    def start(self):
        self._activate_in_context(force=True)
        self.update_operation_context()

    def invoke_tool_with_cache(self, f: Callable, argnames: List[str], args, kwargs):
        if self._current_tool is not None:
            Tracer.push_tool(f, args, kwargs)
            output = f(*args, **kwargs)  # Do nothing if we are handling another tool
            output = Tracer.pop(output)
            return output

        self._current_tool = f
        all_args = parse_all_args(argnames, args, kwargs)
        node_run_id = self._generate_current_node_run_id()
        flow_logger.info(f"Executing node {self._current_node.name}. node run id: {node_run_id}")
        parent_run_id = f"{self._run_id}_{self._line_number}" if self._line_number is not None else self._run_id
        run_info: RunInfo = self._run_tracker.start_node_run(
            node=self._current_node.name,
            flow_run_id=self._run_id,
            parent_run_id=parent_run_id,
            run_id=node_run_id,
            index=self._line_number,
        )

        run_info.index = self._line_number
        run_info.variant_id = self._variant_id

        self._run_tracker.set_inputs(node_run_id, {key: value for key, value in all_args.items() if key != "self"})
        traces = []
        try:
            hit_cache = False
            # Get result from cache. If hit cache, no need to execute f.
            cache_info: CacheInfo = self._cache_manager.calculate_cache_info(self._flow_id, f, args, kwargs)
            if self._current_node.enable_cache and cache_info:
                cache_result: CacheResult = self._cache_manager.get_cache_result(cache_info)
                if cache_result and cache_result.hit_cache:
                    # Assign cached_flow_run_id and cached_run_id.
                    run_info.cached_flow_run_id = cache_result.cached_flow_run_id
                    run_info.cached_run_id = cache_result.cached_run_id
                    result = cache_result.result
                    hit_cache = True

            if not hit_cache:
                Tracer.start_tracing(node_run_id)
                trace = Tracer.push_tool(f, args, kwargs)
                trace.node_name = run_info.node
                result = self.invoke_tool(f, args, kwargs)
                result = Tracer.pop(result)
                traces = Tracer.end_tracing()

            self._current_tool = None
            self._run_tracker.end_run(node_run_id, result=result, traces=traces)
            # Record result in cache so that future run might reuse its result.
            if not hit_cache and self._current_node.enable_cache:
                self._persist_cache(cache_info, run_info)

            flow_logger.info(f"Node {self._current_node.name} completes.")
            return result
        except Exception as e:
            logger.exception(f"Node {self._current_node.name} in line {self._line_number} failed. Exception: {e}.")
            Tracer.pop(error=e)
            if not traces:
                traces = Tracer.end_tracing()
            self._run_tracker.end_run(node_run_id, ex=e, traces=traces)
            raise
        finally:
            self._run_tracker.persist_node_run(run_info)

    def invoke_tool(self, f: Callable, args, kwargs):
        node_name = self._current_node.name if self._current_node else f.__name__
        try:
            logging_name = node_name
            if self._line_number is not None:
                logging_name = f"{node_name} in line {self._line_number}"
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
                return f(*args, **kwargs)
        except PromptflowException as e:
            # All the exceptions from built-in tools are PromptflowException.
            # For these cases, raise the exception directly.
            if f.__module__ is not None:
                e.module = f.__module__
            raise e
        except Exception as e:
            # Otherwise, we assume the error comes from user's tool.
            # For these cases, raise ToolExecutionError, which is classified as UserError
            # and shows stack trace in the error message to make it easy for user to troubleshoot.
            raise ToolExecutionError(node_name=node_name, module=f.__module__) from e

    def end(self):
        self._deactivate_in_context()

    def _persist_cache(self, cache_info: CacheInfo, run_info: RunInfo):
        """Record result in cache storage if hash_id is valid."""
        if cache_info and cache_info.hash_id is not None and len(cache_info.hash_id) > 0:
            try:
                self._cache_manager.persist_result(run_info, cache_info, self._flow_id)
            except Exception as ex:
                # Not a critical path, swallow the exception.
                logging.warning(f"Failed to persist cache result. run_id: {run_info.run_id}. Exception: {ex}")

    def _generate_current_node_run_id(self) -> str:
        node = self._current_node
        if node.aggregation:
            # For reduce node, the id should be constructed by the flow run info run id
            return f"{self._run_id}_{node.name}_reduce"
        if self._line_number is None:
            return f"{self._run_id}_{node.name}_{uuid.uuid4()}"
        return f"{self._run_id}_{node.name}_{self._line_number}"
