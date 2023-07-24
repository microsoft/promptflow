import logging
import uuid
from contextvars import ContextVar
from typing import Callable, List

from promptflow.contracts.flow import Node
from promptflow.contracts.run_info import FlowRunInfo, RunInfo
from promptflow.contracts.run_mode import RunMode
from promptflow.core.cache_manager import AbstractCacheManager, CacheInfo, CacheResult
from promptflow.exceptions import PromptflowException, ToolExecutionError
from promptflow.utils.logger_utils import flow_logger, logger
from promptflow.utils.thread_utils import RepeatLogTimer

from .run_tracker import RunTracker
from .thread_local_singleton import ThreadLocalSingleton
from .tool import parse_all_args
from .api_injector import Tracer


class FlowExecutionContext(ThreadLocalSingleton):
    """The context for a flow execution."""
    CONTEXT_VAR_NAME = "Flow"
    context_var = ContextVar(CONTEXT_VAR_NAME, default=None)

    def __init__(
        self,
        name,
        run_tracker: RunTracker,
        cache_manager: AbstractCacheManager,
        flow_run_info: FlowRunInfo,
        *,
        inputs=None,
        run_mode: RunMode = RunMode.Flow,
    ):
        self._name = name
        self._inputs = inputs or {}
        self._current_tool = None
        self._run_tracker = run_tracker
        self._cache_manager = cache_manager
        # Initialize a dummy flow run info if not provided
        # TODO: Refine the code to avoid using flow run info for flow execution context
        if flow_run_info is None:
            dummy_id = str(uuid.uuid4())
            flow_run_info = run_tracker.start_flow_run(
                flow_id=dummy_id, root_run_id=dummy_id, run_id=dummy_id, parent_run_id=dummy_id
            )
        self._flow_run_info = flow_run_info
        self._run_mode = run_mode
        self._current_node: Node = None

    @property
    def current_node(self) -> Node:
        return self._current_node

    @current_node.setter
    def current_node(self, node: Node):
        self._current_node = node
        self._batch_state = False

    def start(self):
        self._activate_in_context(force=True)

    def invoke_tool_with_cache(self, f: Callable, argnames: List[str], args, kwargs):
        if self._current_tool is not None:
            Tracer.push_tool(f, args, kwargs)
            output = self.invoke_tool(f, args, kwargs)  # Do nothing if we are handling another tool
            Tracer.pop(output)
            return output

        self._current_tool = f
        all_args = parse_all_args(argnames, args, kwargs)
        node_run_id = self._generate_current_node_run_id()
        flow_logger.info(f'Executing node {self._current_node.name}. node run id: {node_run_id}')
        run_info: RunInfo = self._run_tracker.start_node_run(
            node=self._current_node.name,
            flow_run_id=self._flow_run_info.root_run_id,
            parent_run_id=self._flow_run_info.run_id,
            run_id=node_run_id,
            index=self._flow_run_info.index,
        )

        run_info.index = self._flow_run_info.index
        run_info.variant_id = self._flow_run_info.variant_id

        self._run_tracker.set_inputs(node_run_id, {key: value for key, value in all_args.items() if key != "self"})
        traces = []
        try:
            hit_cache = False
            # Get result from cache. If hit cache, no need to execute f.
            cache_info: CacheInfo = self._cache_manager.calculate_cache_info(
                self._flow_run_info.flow_id, f, args, kwargs
            )
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
                result = self.invoke_tool(f, args, kwargs)
                traces = Tracer.end_tracing()

            self._current_tool = None
            self._run_tracker.end_run(node_run_id, result=result, traces=traces)
            # Record result in cache so that future run might reuse its result.
            if not hit_cache and self._current_node.enable_cache:
                self._persist_cache(cache_info, run_info)

            flow_logger.info(f'Node {self._current_node.name} completes.')
            return result
        except Exception as e:
            logger.exception(
                f'Node {self._current_node.name} in line {self._flow_run_info.index} failed. Exception: {e}.')
            if not traces:
                traces = Tracer.end_tracing()
            self._run_tracker.end_run(node_run_id, ex=e, traces=traces)
            raise
        finally:
            # If enable cache, run info should always be persisted so its result is recorded.
            if self._run_mode.persist_node_run or self._current_node.enable_cache:
                self._run_tracker.persist_node_run(self._run_tracker.get_run(node_run_id))

    def invoke_tool(self, f: Callable, args, kwargs):
        node_name = self._current_node.name if self._current_node else f.__name__
        try:
            name = node_name + f' in line {self._flow_run_info.index}' if self._flow_run_info else node_name
            with RepeatLogTimer(interval_seconds=60, logger=logger, func_name=name):
                return f(*args, **kwargs)
        except Exception as e:
            # All the exceptions from built-in tools are PromptflowException.
            # For these cases, raise the exception directly.
            if isinstance(e, PromptflowException):
                raise

            # Otherwise, we assume the error comes from user's tool.
            # For these cases, raise ToolExecutionError, which is classified as UserError
            # and shows stack trace in the error message to make it easy for user to troubleshoot.
            raise ToolExecutionError(node_name=node_name) from e

    def end(self):
        self._deactivate_in_context()

    def _persist_cache(self, cache_info: CacheInfo, run_info: RunInfo):
        """Record result in cache storage if hash_id is valid."""
        if cache_info and cache_info.hash_id is not None and len(cache_info.hash_id) > 0:
            try:
                self._cache_manager.persist_result(run_info, cache_info, self._flow_run_info.flow_id)
            except Exception as ex:
                # Not a critical path, swallow the exception.
                logging.warning(f"Failed to persist cache result. run_id: {run_info.run_id}. Exception: {ex}")

    def _generate_current_node_run_id(self) -> str:
        node = self._current_node
        if node.reduce:
            # For reduce node, the id should be constructed by the flow run info run id
            return f"{self._flow_run_info.run_id}_{node.name}_reduce"
        elif self._flow_run_info.index is None:
            # For line process without index, id should be constructed by the flow run info run id + node name
            return f"{self._flow_run_info.run_id}_{node.name}"
        else:
            # For line process with index, id should be constructed by the flow's parent run id + node name + idx
            return f"{self._flow_run_info.parent_run_id}_{node.name}_{self._flow_run_info.index}"
