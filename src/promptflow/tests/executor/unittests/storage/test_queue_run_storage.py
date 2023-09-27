import pytest

from multiprocessing import Queue
from promptflow.executor._line_execution_process_pool import QueueRunStorage
from promptflow.contracts.run_info import FlowRunInfo
from promptflow.contracts.run_info import RunInfo as NodeRunInfo


@pytest.mark.unittest
class TestLineExecutionProcessPool:
    def test_persist_node_run(self):
        queue = Queue()
        run_storage = QueueRunStorage(queue)
        node_run_info = NodeRunInfo(
            node="node1",
            flow_run_id="flow_run_id",
            run_id="run_id",
            status="status",
            inputs="inputs",
            output="output",
            metrics="metrics",
            error="error",
            parent_run_id="parent_run_id",
            start_time="start_time",
            end_time="end_time",
            index="index",
            api_calls="api_calls",
            variant_id="variant_id",
            cached_run_id="cached_run_id",
            cached_flow_run_id="cached_flow_run_id",
            logs="logs",
            system_metrics="system_metrics",
            result="result",
        )
        run_storage.persist_node_run(node_run_info)
        assert queue.qsize() == 1
        assert queue.get() == node_run_info

    def test_persist_flow_run(self):
        queue = Queue()
        run_storage = QueueRunStorage(queue)
        flow_run_info = FlowRunInfo(
            run_id="run_id",
            status="status",
            inputs="inputs",
            output="output",
            metrics="metrics",
            request="request",
            root_run_id="root_run_id",
            source_run_id="source_run_id",
            flow_id="flow_id",
            error="error",
            parent_run_id="parent_run_id",
            start_time="start_time",
            end_time="end_time",
            index="index",
            api_calls="api_calls",
            variant_id="variant_id",
            system_metrics="system_metrics",
            result="result",
        )
        run_storage.persist_flow_run(flow_run_info)
        assert queue.qsize() == 1
        assert queue.get() == flow_run_info
