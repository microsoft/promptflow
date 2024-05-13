# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import asyncio
import contextvars
import inspect
import os
import threading
import time
import traceback
from asyncio import Task
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

from promptflow._core.flow_execution_context import FlowExecutionContext
from promptflow._core.tools_manager import ToolsManager
from promptflow._utils.logger_utils import flow_logger
from promptflow._utils.thread_utils import ThreadWithContextVars
from promptflow._utils.utils import extract_user_frame_summaries, set_context, try_get_long_running_logging_interval
from promptflow.contracts.flow import Node
from promptflow.executor._dag_manager import DAGManager
from promptflow.executor._errors import LineExecutionTimeoutError, NoNodeExecutedError

PF_ASYNC_NODE_SCHEDULER_EXECUTE_TASK_NAME = "_pf_async_nodes_scheduler.execute"
DEFAULT_TASK_LOGGING_INTERVAL = 60
ASYNC_DAG_MANAGER_COMPLETED = False


class AsyncNodesScheduler:
    def __init__(
        self,
        tools_manager: ToolsManager,
        node_concurrency: int,
    ) -> None:
        self._tools_manager = tools_manager
        self._node_concurrency = node_concurrency
        self._task_start_time = {}
        self._task_last_log_time = {}
        self._dag_manager_completed_event = threading.Event()

    async def execute(
        self,
        nodes: List[Node],
        inputs: Dict[str, Any],
        context: FlowExecutionContext,
        timeout_seconds: Optional[int] = None,
    ) -> Tuple[dict, dict]:
        # Semaphore should be created in the loop, otherwise it will not work.
        loop = asyncio.get_running_loop()
        self._semaphore = asyncio.Semaphore(self._node_concurrency)
        if (interval := try_get_long_running_logging_interval(flow_logger, DEFAULT_TASK_LOGGING_INTERVAL)) is not None:
            monitor = ThreadWithContextVars(
                target=monitor_long_running_coroutine,
                args=(
                    interval,
                    loop,
                    self._task_start_time,
                    self._task_last_log_time,
                    self._dag_manager_completed_event,
                ),
                daemon=True,
            )
            monitor.start()

        # Set the name of scheduler tasks to avoid monitoring its duration
        task = asyncio.current_task()
        task.set_name(PF_ASYNC_NODE_SCHEDULER_EXECUTE_TASK_NAME)

        parent_context = contextvars.copy_context()
        executor = ThreadPoolExecutor(
            max_workers=self._node_concurrency, initializer=set_context, initargs=(parent_context,)
        )
        # Note that we must not use `with` statement to manage the executor.
        # This is because it will always call `executor.shutdown()` when exiting the `with` block.
        # Then the event loop will wait for all tasks to be completed before raising the cancellation error.
        # See reference: https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.Executor
        try:
            outputs = await self._execute_with_thread_pool(executor, nodes, inputs, context, timeout_seconds)
        except asyncio.CancelledError:
            await self.cancel()
            raise
        executor.shutdown()
        return outputs

    async def _execute_with_thread_pool(
        self,
        executor: ThreadPoolExecutor,
        nodes: List[Node],
        inputs: Dict[str, Any],
        context: FlowExecutionContext,
        timeout_seconds: Optional[int] = None,
    ) -> Tuple[dict, dict]:
        flow_logger.info(f"Start to run {len(nodes)} nodes with the current event loop.")
        start_time = time.time()
        dag_manager = DAGManager(nodes, inputs)
        task2nodes = self._execute_nodes(dag_manager, context, executor)
        while not dag_manager.completed():
            remaining_timeout = None if timeout_seconds is None else timeout_seconds - (time.time() - start_time)
            task = asyncio.create_task(self._wait_and_complete_nodes(task2nodes, dag_manager))
            try:
                task2nodes = await asyncio.wait_for(task, remaining_timeout)
            except asyncio.TimeoutError:
                flow_logger.warning(f"Line execution timeout after {timeout_seconds} seconds.")
                await self.cancel_tasks(task2nodes.keys())
                raise LineExecutionTimeoutError(context._line_number, timeout_seconds)
            submitted_tasks2nodes = self._execute_nodes(dag_manager, context, executor)
            task2nodes.update(submitted_tasks2nodes)
        # Set the event to notify the monitor thread to exit
        # Ref: https://docs.python.org/3/library/threading.html#event-objects
        self._dag_manager_completed_event.set()
        for node in dag_manager.bypassed_nodes:
            dag_manager.completed_nodes_outputs[node] = None
        return dag_manager.completed_nodes_outputs, dag_manager.bypassed_nodes

    async def cancel_tasks(self, tasks: List[asyncio.Task]):
        for task in tasks:
            if not task.done():
                task.cancel()
        cancel_timeout = 1
        # Wait at most 1 second for the tasks to cleanup
        await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED, timeout=cancel_timeout)

    async def _wait_and_complete_nodes(self, task2nodes: Dict[Task, Node], dag_manager: DAGManager) -> Dict[Task, Node]:
        if not task2nodes:
            raise NoNodeExecutedError("No nodes are ready for execution, but the flow is not completed.")
        tasks = [task for task in task2nodes]
        for task in tasks:
            self._task_start_time[task] = time.time()
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
            self._create_node_task(node, dag_manager, context, executor): node for node in dag_manager.pop_ready_nodes()
        }

    async def run_task_with_semaphore(self, coroutine):
        async with self._semaphore:
            return await coroutine

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
            # For async task, it will not be executed before calling create_task.
            task = context.invoke_tool_async(node, f, kwargs)
        else:
            # For sync task, convert it to async task and run it in executor thread.
            # Even though the task is put to the thread pool, thread.start will only be triggered after create_task.
            task = self._sync_function_to_async_task(executor, context, node, f, kwargs)
        # Set the name of the task to the node name for debugging purpose
        # It does not need to be unique by design.
        # Wrap the coroutine in a task with asyncio.create_task to schedule it for event loop execution
        # The task is created and added to the event loop, but the exact execution depends on loop's scheduling
        return asyncio.create_task(self.run_task_with_semaphore(task), name=node.name)

    @staticmethod
    async def _sync_function_to_async_task(
        executor: ThreadPoolExecutor,
        context: FlowExecutionContext,
        node,
        f,
        kwargs,
    ):
        # The task will not be executed before calling create_task.
        return await asyncio.get_running_loop().run_in_executor(executor, context.invoke_tool, node, f, kwargs)

    async def cancel(self):
        flow_logger.info("Cancel requested, monitoring coroutines after cancellation.")
        loop = asyncio.get_running_loop()
        monitor = ThreadWithContextVars(target=monitor_coroutine_after_cancellation, args=(loop,))
        monitor.start()


def log_stack_recursively(task: asyncio.Task, elapse_time: float):
    """Recursively log the frame of a task or coroutine.
    Traditional stacktrace would stop at the first awaited nested inside the coroutine.

    :param task: Task to log
    :type task_or_coroutine: asyncio.Task
    :param elapse_time: Seconds elapsed since the task started
    :type elapse_time: float
    """
    # We cannot use task.get_stack() to get the stack, because only one stack frame is
    # returned for a suspended coroutine because of the implementation of CPython
    # Ref: https://github.com/python/cpython/blob/main/Lib/asyncio/tasks.py
    # "only one stack frame is returned for a suspended coroutine."
    task_or_coroutine = task
    frame_summaries = []
    # Collect frame_summaries along async call chain
    while True:
        if isinstance(task_or_coroutine, asyncio.Task):
            # For a task, get the coroutine it's running
            coroutine: asyncio.coroutine = task_or_coroutine.get_coro()
        elif asyncio.iscoroutine(task_or_coroutine):
            coroutine = task_or_coroutine
        else:
            break

        frame = coroutine.cr_frame
        stack_summary: traceback.StackSummary = traceback.extract_stack(frame)
        frame_summaries.extend(stack_summary)
        task_or_coroutine = coroutine.cr_await

    # Format the frame summaries to warning message
    if frame_summaries:
        user_frame_summaries = extract_user_frame_summaries(frame_summaries)
        stack_messages = traceback.format_list(user_frame_summaries)
        all_stack_message = "".join(stack_messages)
        task_msg = (
            f"Task {task.get_name()} has been running for {elapse_time:.0f} seconds,"
            f" stacktrace:\n{all_stack_message}"
        )
        flow_logger.warning(task_msg)


def monitor_long_running_coroutine(
    logging_interval: int,
    loop: asyncio.AbstractEventLoop,
    task_start_time: dict,
    task_last_log_time: dict,
    dag_manager_completed_event: threading.Event,
):
    flow_logger.info("monitor_long_running_coroutine started")

    while not dag_manager_completed_event.is_set():
        running_tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
        # get duration of running tasks
        for task in running_tasks:
            # Do not monitor the scheduler task
            if task.get_name() == PF_ASYNC_NODE_SCHEDULER_EXECUTE_TASK_NAME:
                continue
            # Do not monitor sync tools, since they will run in executor thread and will
            # be monitored by RepeatLogTimer.
            task_stacks = task.get_stack()
            if (
                task_stacks
                and task_stacks[-1].f_code
                and task_stacks[-1].f_code.co_name == AsyncNodesScheduler._sync_function_to_async_task.__name__
            ):
                continue
            if task_start_time.get(task) is None:
                flow_logger.warning(f"task {task.get_name()} has no start time, which should not happen")
            else:
                duration = time.time() - task_start_time[task]
                if duration > logging_interval:
                    if (
                        task_last_log_time.get(task) is None
                        or time.time() - task_last_log_time[task] > logging_interval
                    ):
                        log_stack_recursively(task, duration)
                        task_last_log_time[task] = time.time()
        time.sleep(1)


def monitor_coroutine_after_cancellation(loop: asyncio.AbstractEventLoop):
    """Exit the process when all coroutines are done.
    We add this function because if a sync tool is running in async mode,
    the task will be cancelled after receiving SIGINT,
    but the thread will not be terminated and blocks the program from exiting.
    :param loop: event loop of main thread
    :type loop: asyncio.AbstractEventLoop
    """
    # TODO: Use environment variable to ensure it is flow test scenario to avoid unexpected exit.
    # E.g. Customer is integrating Promptflow in their own code, and they want to handle SIGINT by themselves.
    max_wait_seconds = os.environ.get("PF_WAIT_SECONDS_AFTER_CANCELLATION", 30)

    all_tasks_are_done = False
    exceeded_wait_seconds = False

    thread_start_time = time.time()
    flow_logger.info(f"Start to monitor coroutines after cancellation, max wait seconds: {max_wait_seconds}s")

    while not all_tasks_are_done and not exceeded_wait_seconds:
        # For sync tool running in async mode, the task will be cancelled,
        # but the thread will not be terminated, we exit the program despite of it.
        # TODO: Detect whether there is any sync tool running in async mode,
        # if there is none, avoid sys.exit and let the program exit gracefully.
        all_tasks_are_done = all(task.done() for task in asyncio.all_tasks(loop))
        if all_tasks_are_done:
            flow_logger.info("All coroutines are done. Exiting.")
            # We cannot ensure persist_flow_run is called before the process exits in the case that there is
            # non-daemon thread running, sleep for 3 seconds as a best effort.
            # If the caller wants to ensure flow status is cancelled in storage, it should check the flow status
            # after timeout and set the flow status to Cancelled.
            time.sleep(3)
            # Use os._exit instead of sys.exit, so that the process can stop without
            # waiting for the thread created by run_in_executor to finish.
            # sys.exit: https://docs.python.org/3/library/sys.html#sys.exit
            # Raise a SystemExit exception, signaling an intention to exit the interpreter.
            # Specifically, it does not exit non-daemon thread
            # os._exit https://docs.python.org/3/library/os.html#os._exit
            # Exit the process with status n, without calling cleanup handlers, flushing stdio buffers, etc.
            # Specifically, it stops process without waiting for non-daemon thread.
            os._exit(0)

        exceeded_wait_seconds = time.time() - thread_start_time > max_wait_seconds
        time.sleep(1)

    if exceeded_wait_seconds:
        if not all_tasks_are_done:
            flow_logger.info(
                f"Not all coroutines are done within {max_wait_seconds}s"
                " after cancellation. Exiting the process despite of them."
                " Please config the environment variable"
                " PF_WAIT_SECONDS_AFTER_CANCELLATION if your tool needs"
                " more time to clean up after cancellation."
            )
            remaining_tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
            flow_logger.info(f"Remaining tasks: {[task.get_name() for task in remaining_tasks]}")
        time.sleep(3)
        os._exit(0)
