# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import asyncio
from asyncio import Task
from typing import Dict, List, Tuple, Any

from promptflow._core.flow_execution_context import FlowExecutionContext
from promptflow._core.tools_manager import ToolsManager
from promptflow._utils.logger_utils import flow_logger
from promptflow.contracts.flow import Node
from promptflow.executor._dag_manager import DAGManager
from promptflow.executor._errors import NoNodeExecutedError


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
        flow_logger.info(f"Start to run {len(nodes)} nodes with the current event loop.")
        dag_manager = DAGManager(nodes, inputs)
        loop = asyncio.get_event_loop()
        task2nodes = self._execute_nodes(loop, dag_manager, context)
        while not dag_manager.completed():
            task2nodes = await self._wait_and_complete_nodes(task2nodes, dag_manager)
            submitted_tasks2nodes = self._execute_nodes(loop, dag_manager, context)
            task2nodes.update(submitted_tasks2nodes)
        for node in dag_manager.bypassed_nodes:
            dag_manager.completed_nodes_outputs[node] = None
        return dag_manager.completed_nodes_outputs, dag_manager.bypassed_nodes

    async def _wait_and_complete_nodes(
        self,
        task2nodes: Dict[Task, Node],
        dag_manager: DAGManager
    ) -> Dict[Task, Node]:
        if not task2nodes:
            raise NoNodeExecutedError("No nodes are ready for execution, but the flow is not completed.")
        tasks = [task for task in task2nodes]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        dag_manager.complete_nodes({
            task2nodes[task].name: task.result()
            for task in done
        })
        for task in done:
            del task2nodes[task]
        return task2nodes

    def _execute_nodes(
        self,
        loop: asyncio.AbstractEventLoop,
        dag_manager: DAGManager,
        context: FlowExecutionContext,
    ) -> Dict[Task[Any], Node]:
        # Bypass nodes and update node run info until there are no nodes to bypass
        nodes_to_bypass = dag_manager.pop_bypassable_nodes()
        while nodes_to_bypass:
            for node in nodes_to_bypass:
                node_outputs = dag_manager.get_bypassed_node_outputs(node)
                context.bypass_node(node, node_outputs)
            nodes_to_bypass = dag_manager.pop_bypassable_nodes()
        # Create tasks for ready nodes
        return {
            self._create_node_task(loop, node, dag_manager, context): node
            for node in dag_manager.pop_ready_nodes()
        }

    def _create_node_task(
        self,
        loop: asyncio.AbstractEventLoop,
        node: Node,
        dag_manager: DAGManager,
        context: FlowExecutionContext,
    ) -> Task[Any]:
        f = self._tools_manager.get_tool(node.name)
        kwargs = dag_manager.get_node_valid_inputs(node, f)
        task = context.invoke_tool_async(node, f, kwargs)
        task = loop.create_task(task)
        return task
