# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import asyncio
import contextvars
import inspect
import os
import signal
import threading
import time
from concurrent import futures
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

from promptflow._core.flow_execution_context import FlowExecutionContext
from promptflow._core.tools_manager import ToolsManager
from promptflow._utils.logger_utils import flow_logger
from promptflow._utils.thread_utils import ThreadWithContextVars
from promptflow._utils.utils import set_context
from promptflow.contracts.flow import Node
from promptflow.executor._dag_manager import DAGManager
from promptflow.executor._errors import LineExecutionTimeoutError, NoNodeExecutedError

RUN_FLOW_NODES_LINEARLY = 1
DEFAULT_CONCURRENCY_BULK = 2
DEFAULT_CONCURRENCY_FLOW = 16


def signal_handler(sig, frame):
    """
    In main thread, we raise KeyboardInterrupt to mark run as cancelled and exit execution.
    But the process may not exit immediately because there are worker threads running from ThreadPoolExecutor.
    So, start new worker thread and use os._exit to guarantee the process could exit after delay time.
    """

    flow_logger.info(f"Received signal {sig}({signal.Signals(sig).name}), start to exit sync flow execution.")

    def exit_process_with_delay():
        # Adding 3 seconds delay here to let the main thread to finish the cleanup work, such as exporting spans.
        time.sleep(3)
        # Use os._exit instead of sys.exit, so that the process can stop without
        # waiting for the thread created by ThreadPoolExecutor to finish.
        # sys.exit: https://docs.python.org/3/library/sys.html#sys.exit
        # Raise a SystemExit exception, signaling an intention to exit the interpreter.
        # Specifically, it does not exit non-daemon thread
        # os._exit https://docs.python.org/3/library/os.html#os._exit
        # Exit the process with status n, without calling cleanup handlers, flushing stdio buffers, etc.
        # Specifically, it stops process without waiting for non-daemon thread.
        os._exit(0)

    monitor = ThreadWithContextVars(target=exit_process_with_delay)
    monitor.start()
    raise KeyboardInterrupt


class FlowNodesScheduler:
    def __init__(
        self,
        tools_manager: ToolsManager,
        inputs: Dict,
        nodes_from_invoker: List[Node],
        node_concurrency: int,
        context: FlowExecutionContext,
    ) -> None:
        self._tools_manager = tools_manager
        self._future_to_node: Dict[Future, Node] = {}
        self._node_concurrency = min(node_concurrency, DEFAULT_CONCURRENCY_FLOW)
        flow_logger.info(f"Start to run {len(nodes_from_invoker)} nodes with concurrency level {node_concurrency}.")
        self._dag_manager = DAGManager(nodes_from_invoker, inputs)
        self._context = context

    def wait_within_timeout(self, execution_event: threading.Event, timeout: int):
        flow_logger.info(f"Timeout task is scheduled to wait for {timeout} seconds.")
        signal = execution_event.wait(timeout=timeout)
        if signal:
            flow_logger.info("Timeout task is cancelled because the execution is finished.")
        else:
            flow_logger.warning(f"Timeout task timeouted after waiting for {timeout} seconds.")

    def execute(
        self,
        line_timeout_sec: Optional[int] = None,
    ) -> Tuple[dict, dict]:
        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        else:
            flow_logger.info(
                "Current thread is not main thread, skip signal handler registration in AsyncNodesScheduler."
            )
        parent_context = contextvars.copy_context()
        # If we use `with ThreadPoolExecutor`, the __exit__ method will be called to wait all threads are finished.
        # Then any exception raised in the threads will be blocked, which is unexpected.
        # So, we just create the executor and shutdown it manually.
        executor = ThreadPoolExecutor(
            max_workers=self._node_concurrency, initializer=set_context, initargs=(parent_context,)
        )
        self._execute_nodes(executor)
        timeout_task = None
        event = threading.Event()
        if line_timeout_sec is not None:
            timeout_task = executor.submit(self.wait_within_timeout, event, line_timeout_sec)
        try:
            while not self._dag_manager.completed():
                if not self._future_to_node:
                    raise NoNodeExecutedError("No nodes are ready for execution, but the flow is not completed.")
                tasks_to_wait = list(self._future_to_node.keys())
                if timeout_task is not None:
                    tasks_to_wait.append(timeout_task)
                completed_futures_with_wait, _ = futures.wait(tasks_to_wait, return_when=futures.FIRST_COMPLETED)
                completed_futures = [f for f in completed_futures_with_wait if f in self._future_to_node]
                self._dag_manager.complete_nodes(self._collect_outputs(completed_futures))
                for each_future in completed_futures:
                    del self._future_to_node[each_future]
                if timeout_task and timeout_task.done():
                    raise LineExecutionTimeoutError(self._context._line_number, line_timeout_sec)
                self._execute_nodes(executor)
            event.set()
            executor.shutdown()
        except Exception as e:
            err_msg = "Flow execution has failed."
            if isinstance(e, LineExecutionTimeoutError):
                err_msg = f"Line execution timeout after {line_timeout_sec} seconds."
                self._context.cancel_node_runs(err_msg)
            node_names = ",".join(node.name for node in self._future_to_node.values())
            flow_logger.error(f"{err_msg} Cancelling all running nodes: {node_names}.")
            for unfinished_future in self._future_to_node.keys():
                # We can't cancel running tasks here, only pending tasks could be cancelled.
                unfinished_future.cancel()
            raise e
        finally:
            # When meet exception, mark event to exit timeout task.
            event.set()
            # Use shutdown(wait=False) to ignore running threads.
            # When meet exception, we want to exit the execution and mark it as failed/cancelled,
            # so don't need to wait for running threads.
            # If not meet exception, below shutdown will not take any effect.
            executor.shutdown(wait=False)
        for node in self._dag_manager.bypassed_nodes:
            self._dag_manager.completed_nodes_outputs[node] = None
        return self._dag_manager.completed_nodes_outputs, self._dag_manager.bypassed_nodes

    def _execute_nodes(self, executor: ThreadPoolExecutor):
        # Skip nodes and update node run info until there are no nodes to bypass
        nodes_to_bypass = self._dag_manager.pop_bypassable_nodes()
        while nodes_to_bypass:
            for node in nodes_to_bypass:
                self._context.bypass_node(node)
            nodes_to_bypass = self._dag_manager.pop_bypassable_nodes()

        # Submit nodes that are ready to run
        nodes_to_exec = self._dag_manager.pop_ready_nodes()
        if nodes_to_exec:
            self._submit_nodes(executor, nodes_to_exec)

    def _collect_outputs(self, completed_futures: List[Future]):
        completed_nodes_outputs = {}
        for each_future in completed_futures:
            each_node_result = each_future.result()
            each_node = self._future_to_node[each_future]
            completed_nodes_outputs[each_node.name] = each_node_result
        return completed_nodes_outputs

    def _submit_nodes(self, executor: ThreadPoolExecutor, nodes):
        for each_node in nodes:
            future = executor.submit(self._exec_single_node_in_thread, (each_node, self._dag_manager))
            self._future_to_node[future] = each_node

    def _exec_single_node_in_thread(self, args: Tuple[Node, DAGManager]):
        node, dag_manager = args
        # We are using same run tracker and cache manager for all threads, which may not thread safe.
        # But for bulk run scenario, we've doing this for a long time, and it works well.
        context = self._context
        f = self._tools_manager.get_tool(node.name)
        kwargs = dag_manager.get_node_valid_inputs(node, f)
        if inspect.iscoroutinefunction(f):
            # TODO: Run async functions in flow level event loop
            result = asyncio.run(context.invoke_tool_async(node, f, kwargs=kwargs))
        else:
            result = context.invoke_tool(node, f, kwargs=kwargs)
        return result
