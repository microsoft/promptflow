# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import asyncio
import inspect
import contextvars
from asyncio import Task
from typing import Any, Dict, List, Tuple

from promptflow._core.tools_manager import ToolsManager
from promptflow._utils.logger_utils import flow_logger
from promptflow._utils.utils import set_context
from promptflow.contracts.flow import Node
from promptflow.executor._dag_manager import DAGManager
from promptflow.executor._errors import NoNodeExecutedError
from promptflow.executor._tool_invoker import DefaultToolInvoker
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
        invoker: DefaultToolInvoker,
    ) -> Tuple[dict, dict]:
        parent_context = contextvars.copy_context()
        with ThreadPoolExecutor(
            max_workers=self._node_concurrency, initializer=set_context, initargs=(parent_context,)
        ) as executor:
            return await self._execute_with_thread_pool(executor, nodes, inputs, invoker)

    async def _execute_with_thread_pool(
        self,
        executor: ThreadPoolExecutor,
        nodes: List[Node],
        inputs: Dict[str, Any],
        invoker: DefaultToolInvoker,
    ) -> Tuple[dict, dict]:
        flow_logger.info(f"Start to run {len(nodes)} nodes with the current event loop.")
        dag_manager = DAGManager(nodes, inputs)
        task2nodes = self._execute_nodes(dag_manager, invoker, executor)
        while not dag_manager.completed():
            task2nodes = await self._wait_and_complete_nodes(task2nodes, dag_manager)
            submitted_tasks2nodes = self._execute_nodes(dag_manager, invoker, executor)
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
        invoker: DefaultToolInvoker,
        executor: ThreadPoolExecutor,
    ) -> Dict[Task, Node]:
        # Bypass nodes and update node run info until there are no nodes to bypass
        nodes_to_bypass = dag_manager.pop_bypassable_nodes()
        while nodes_to_bypass:
            for node in nodes_to_bypass:
                invoker.bypass_node(node)
            nodes_to_bypass = dag_manager.pop_bypassable_nodes()
        # Create tasks for ready nodes
        return {
            self._create_node_task(node, dag_manager, invoker, executor): node
            for node in dag_manager.pop_ready_nodes()
        }

    def _create_node_task(
        self,
        node: Node,
        dag_manager: DAGManager,
        invoker: DefaultToolInvoker,
        executor: ThreadPoolExecutor,
    ) -> Task:
        f = self._tools_manager.get_tool(node.name)
        kwargs = dag_manager.get_node_valid_inputs(node, f)
        if inspect.iscoroutinefunction(f):
            task = invoker.invoke_tool_async(node, f, kwargs)
        else:
            task = self._sync_function_to_async_task(executor, invoker, node, f, kwargs)
        return asyncio.create_task(task)

    @staticmethod
    def _invoke_sync_tool(invoker, node, f, kwargs):
        try:
            invoker.start()
            invoker.current_node = node
            result = f(**kwargs)
            invoker.current_node = None
            return result
        finally:
            invoker.end()

    @staticmethod
    async def _sync_function_to_async_task(
        executor: ThreadPoolExecutor,
        invoker, node,
        f,
        kwargs,
    ):
        return await asyncio.get_running_loop().run_in_executor(
            executor, AsyncNodesScheduler._invoke_sync_tool, invoker, node, f, kwargs
        )
