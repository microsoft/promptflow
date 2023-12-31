# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import asyncio
import inspect
import contextvars
import os
import signal
import threading
import time
from asyncio import Task
from typing import Any, Dict, List, Tuple

from promptflow._core.flow_execution_context import FlowExecutionContext
from promptflow._core.tools_manager import ToolsManager
from promptflow._utils.logger_utils import flow_logger
from promptflow._utils.utils import set_context
from promptflow.contracts.flow import Node
from promptflow.executor._dag_manager import DAGManager
from promptflow.executor._errors import NoNodeExecutedError
from concurrent.futures import ThreadPoolExecutor


class AsyncNodesScheduler:
    def __init__(
        self,
        tools_manager: ToolsManager,
        node_concurrency: int,
    ) -> None:
        self._tools_manager = tools_manager
        # TODO: Add concurrency control in execution
        self._node_concurrency = node_concurrency

    async def execute(
        self,
        nodes: List[Node],
        inputs: Dict[str, Any],
        context: FlowExecutionContext,
    ) -> Tuple[dict, dict]:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        parent_context = contextvars.copy_context()
        executor = ThreadPoolExecutor(
            max_workers=self._node_concurrency, initializer=set_context, initargs=(parent_context,)
        )
        # Note that we must not use `with` statement to manage the executor.
        # This is because it will always call `executor.shutdown()` when exiting the `with` block.
        # Then the event loop will wait for all tasks to be completed before raising the cancellation error.
        # See reference: https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.Executor
        outputs = await self._execute_with_thread_pool(executor, nodes, inputs, context)
        executor.shutdown()
        return outputs

    async def _execute_with_thread_pool(
        self,
        executor: ThreadPoolExecutor,
        nodes: List[Node],
        inputs: Dict[str, Any],
        context: FlowExecutionContext,
    ) -> Tuple[dict, dict]:
        flow_logger.info(f"Start to run {len(nodes)} nodes with the current event loop.")
        dag_manager = DAGManager(nodes, inputs)
        task2nodes = self._execute_nodes(dag_manager, context, executor)
        while not dag_manager.completed():
            task2nodes = await self._wait_and_complete_nodes(task2nodes, dag_manager)
            submitted_tasks2nodes = self._execute_nodes(dag_manager, context, executor)
            task2nodes.update(submitted_tasks2nodes)
        for node in dag_manager.bypassed_nodes:
            dag_manager.completed_nodes_outputs[node] = None
        return dag_manager.completed_nodes_outputs, dag_manager.bypassed_nodes

    async def _wait_and_complete_nodes(self, task2nodes: Dict[Task, Node], dag_manager: DAGManager) -> Dict[Task, Node]:
        if not task2nodes:
            raise NoNodeExecutedError("No nodes are ready for execution, but the flow is not completed.")
        tasks = [task for task in task2nodes]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        dag_manager.complete_nodes({task2nodes[task].name: task.result() for task in done})
        for task in done:
            del task2nodes[task]
        return task2nodes

    def _execute_nodes(
        self,
        dag_manager: DAGManager,
        context: FlowExecutionContext,
        executor: ThreadPoolExecutor,
    ) -> Dict[Task, Node]:
        # Bypass nodes and update node run info until there are no nodes to bypass
        nodes_to_bypass = dag_manager.pop_bypassable_nodes()
        while nodes_to_bypass:
            for node in nodes_to_bypass:
                context.bypass_node(node)
            nodes_to_bypass = dag_manager.pop_bypassable_nodes()
        # Create tasks for ready nodes
        return {
            self._create_node_task(node, dag_manager, context, executor): node
            for node in dag_manager.pop_ready_nodes()
        }

    def _create_node_task(
        self,
        node: Node,
        dag_manager: DAGManager,
        context: FlowExecutionContext,
        executor: ThreadPoolExecutor,
    ) -> Task:
        f = self._tools_manager.get_tool(node.name)
        kwargs = dag_manager.get_node_valid_inputs(node, f)
        if inspect.iscoroutinefunction(f):
            task = context.invoke_tool_async(node, f, kwargs)
        else:
            task = self._sync_function_to_async_task(executor, context, node, f, kwargs)
        # Set the name of the task to the node name for debugging purpose
        # It does not need to be unique by design.
        return asyncio.create_task(task, name=node.name)

    @staticmethod
    async def _sync_function_to_async_task(
        executor: ThreadPoolExecutor,
        context: FlowExecutionContext, node,
        f,
        kwargs,
    ):
        return await asyncio.get_running_loop().run_in_executor(
            executor, context.invoke_tool, node, f, kwargs
        )


def signal_handler(sig, frame):
    """
    Start a thread to monitor coroutines after receiving signal.
    """
    flow_logger.info(f"Received signal {sig}({signal.Signals(sig).name}),"
                     " start coroutint monitor thread.")
    loop = asyncio.get_running_loop()
    monitor = threading.Thread(target=monitor_coroutine_after_cancellation, args=(loop,))
    monitor.start()
    raise KeyboardInterrupt


def monitor_coroutine_after_cancellation(loop: asyncio.AbstractEventLoop):
    """Exit the process when all coroutines are done.
    We add this function because if a sync tool is running in async mode,
    the task will be cancelled after receiving SIGINT,
    but the thread will not be terminated and blocks the program from exiting.
    :param loop: event loop of main thread
    :type loop: asyncio.AbstractEventLoop
    """
    # TODO: Use environment variable to ensure it is flow test / node test scenario
    # to avoid unexpected exit.
    max_wait_seconds = os.environ.get("PF_WAIT_SECONDS_AFTER_CANCELLATION", 30)

    all_tasks_are_done = False
    exceeded_wait_seconds = False

    thread_start_time = time.time()
    flow_logger.info(f"Start to monitor coroutines after cancellation, max wait seconds: {max_wait_seconds}s")

    while not all_tasks_are_done and not exceeded_wait_seconds:
        # For sync tool running in async mode, the task will be cancelled,
        # but the thread will not be terminated, we exit the program despite of it.
        # TODO: Detect whether there is any sync tool running in async mode,
        # if there is none, avoid sys._exit and let the program exit gracefully.
        all_tasks_are_done = all(task.done() for task in asyncio.all_tasks(loop))
        if all_tasks_are_done:
            flow_logger.info("All coroutines are done. Exiting.")
            os._exit(0)

        exceeded_wait_seconds = time.time() - thread_start_time > max_wait_seconds
        time.sleep(1)

    if exceeded_wait_seconds and not all_tasks_are_done:
        flow_logger.info(f"Not all coroutines are done within {max_wait_seconds}s"
                         " after cancellation. Exiting the process despite of them."
                         " Please config the environment variable"
                         " PF_WAIT_SECONDS_AFTER_CANCELLATION if your tool needs"
                         " more time to clean up after cancellation.")
        remaining_tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
        flow_logger.info(f"Remaining tasks: {[task.get_name() for task in remaining_tasks]}")
        os._exit(0)
