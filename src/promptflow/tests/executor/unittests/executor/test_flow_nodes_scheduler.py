from concurrent.futures import Future
from typing import Callable
from unittest.mock import MagicMock

import pytest

from promptflow._core.flow_execution_context import FlowExecutionContext
from promptflow.contracts.flow import Node
from promptflow.executor._dag_manager import DAGManager
from promptflow.executor._flow_nodes_scheduler import (
    DEFAULT_CONCURRENCY_BULK,
    DEFAULT_CONCURRENCY_FLOW,
    FlowNodesScheduler,
    NoNodeExecutedError,
)


@pytest.mark.unittest
class TestFlowNodesScheduler:
    def setup_method(self):
        # Define mock objects and methods
        self.tools_manager = MagicMock()
        self.context = MagicMock(spec=FlowExecutionContext)
        self.context.invoke_tool.side_effect = lambda _, func, kwargs: func(**kwargs)
        self.scheduler = FlowNodesScheduler(self.tools_manager, {}, [], DEFAULT_CONCURRENCY_BULK, self.context)

    def test_maximun_concurrency(self):
        scheduler = FlowNodesScheduler(self.tools_manager, {}, [], 1000, self.context)
        assert scheduler._node_concurrency == DEFAULT_CONCURRENCY_FLOW

    def test_collect_outputs(self):
        future1 = Future()
        future1.set_result("output1")
        future2 = Future()
        future2.set_result("output2")

        node1 = MagicMock(spec=Node)
        node1.name = "node1"
        node2 = MagicMock(spec=Node)
        node2.name = "node2"
        self.scheduler._future_to_node = {future1: node1, future2: node2}

        completed_nodes_outputs = self.scheduler._collect_outputs([future1, future2])

        assert completed_nodes_outputs == {"node1": future1.result(), "node2": future2.result()}

    def test_bypass_nodes(self):
        executor = MagicMock()

        dag_manager = MagicMock(spec=DAGManager)
        node1 = MagicMock(spec=Node)
        node1.name = "node1"
        # The return value will be a list with one item for the first time.
        # Will be a list without item for the second time.
        dag_manager.pop_bypassable_nodes.side_effect = ([node1], [])
        self.scheduler._dag_manager = dag_manager
        self.scheduler._execute_nodes(executor)
        self.scheduler._context.bypass_node.assert_called_once_with(node1)

    def test_submit_nodes(self):
        executor = MagicMock()

        dag_manager = MagicMock(spec=DAGManager)
        node1 = MagicMock(spec=Node)
        node1.name = "node1"
        dag_manager.pop_bypassable_nodes.return_value = []
        # The return value will be a list with one item for the first time.
        # Will be a list without item for the second time.
        dag_manager.pop_ready_nodes.return_value = [node1]
        self.scheduler._dag_manager = dag_manager
        self.scheduler._execute_nodes(executor)
        self.scheduler._context.bypass_node.assert_not_called()
        assert node1 in self.scheduler._future_to_node.values()

    def test_future_cancelled_for_exception(self):
        dag_manager = MagicMock(spec=DAGManager)
        self.scheduler._dag_manager = dag_manager
        dag_manager.completed.return_value = False
        dag_manager.pop_bypassable_nodes.return_value = []
        dag_manager.pop_ready_nodes.return_value = []

        failed_future = Future()
        failed_future.set_exception(Exception("test"))
        from concurrent.futures._base import CANCELLED, FINISHED

        failed_future._state = FINISHED
        cancelled_future = Future()

        node1 = MagicMock(spec=Node)
        node1.name = "node1"
        node2 = MagicMock(spec=Node)
        node2.name = "node2"
        self.scheduler._future_to_node = {failed_future: node1, cancelled_future: node2}
        try:
            self.scheduler.execute()
        except Exception:
            pass

        # Assert another future is cancelled.
        assert CANCELLED in cancelled_future._state

    def test_success_result(self):
        dag_manager = MagicMock(spec=DAGManager)
        finished_future = Future()
        finished_future.set_result("output1")
        finished_node = MagicMock(spec=Node)
        finished_node.name = "node1"
        self.scheduler._dag_manager = dag_manager
        self.scheduler._future_to_node = {finished_future: finished_node}
        # No more nodes need to run.
        dag_manager.pop_bypassable_nodes.return_value = []
        dag_manager.pop_ready_nodes.return_value = []
        dag_manager.completed.side_effect = (False, True)
        bypassed_node_result = {"bypassed_node": "output2"}
        dag_manager.bypassed_nodes = bypassed_node_result
        completed_node_result = {"completed_node": "output1"}
        dag_manager.completed_nodes_outputs = completed_node_result

        result = self.scheduler.execute()
        dag_manager.complete_nodes.assert_called_once_with({"node1": "output1"})
        assert result == (completed_node_result, bypassed_node_result)

    def test_no_nodes_to_run(self):
        dag_manager = MagicMock(spec=DAGManager)
        dag_manager.pop_bypassable_nodes.return_value = []
        dag_manager.pop_ready_nodes.return_value = []
        dag_manager.completed.return_value = False
        self.scheduler._dag_manager = dag_manager
        with pytest.raises(NoNodeExecutedError) as _:
            self.scheduler.execute()

    def test_execute_single_node(self):
        node_to_run = MagicMock(spec=Node)
        node_to_run.name = "node1"
        mock_callable = MagicMock(spec=Callable)
        mock_callable.return_value = "output1"
        self.scheduler._tools_manager.get_tool.return_value = mock_callable
        dag_manager = MagicMock(spec=DAGManager)
        dag_manager.get_node_valid_inputs.return_value = {"input": 1}
        result = self.scheduler._exec_single_node_in_thread((node_to_run, dag_manager))
        mock_callable.assert_called_once_with(**{"input": 1})
        assert result == "output1"
