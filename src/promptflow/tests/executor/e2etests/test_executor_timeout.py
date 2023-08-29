import uuid

import pytest

from promptflow._utils.dataclass_serializer import serialize
from promptflow.contracts.run_info import FlowRunInfo
from promptflow.contracts.run_info import RunInfo as NodeRunInfo
from promptflow.contracts.run_info import Status
from promptflow.executor import FlowExecutor
from promptflow.executor.flow_executor import BulkResult, LineResult
from promptflow.storage import AbstractRunStorage

from ..utils import get_flow_sample_inputs, get_yaml_file

SAMPLE_FLOW = "web_classification_no_variants"
SAMPLE_EVAL_FLOW = "classification_accuracy_evaluation"
ONE_LINE_OF_BULK_TEST_TIMEOUT = "one_line_of_bulktest_timeout"


class MemoryRunStorage(AbstractRunStorage):
    def __init__(self):
        self._node_runs = {}
        self._flow_runs = {}

    def persist_flow_run(self, run_info: FlowRunInfo):
        self._flow_runs[run_info.run_id] = run_info

    def persist_node_run(self, run_info: NodeRunInfo):
        self._node_runs[run_info.run_id] = run_info


@pytest.mark.usefixtures("use_secrets_config_file", "dev_connections")
@pytest.mark.e2etest
class TestExecutor:
    def get_line_inputs(self, flow_folder=""):
        if flow_folder:
            inputs = self.get_bulk_inputs(flow_folder)
            return inputs[0]
        return {
            "url": "https://www.apple.com/shop/buy-iphone/iphone-14",
            "text": "some_text",
        }

    def get_bulk_inputs(self, nlinee=4, flow_folder=""):
        if flow_folder:
            inputs = get_flow_sample_inputs(flow_folder)
            if isinstance(inputs, list) and len(inputs) > 0:
                return inputs
            elif isinstance(inputs, dict):
                return [inputs]
            else:
                raise Exception(f"Invalid type of bulk input: {inputs}")
        return [self.get_line_inputs() for _ in range(nlinee)]

    def skip_serp(self, flow_folder, dev_connections):
        serp_required_flows = ["package_tools"]
        #  Real key is usually more than 32 chars
        if flow_folder in serp_required_flows and len(dev_connections.get("serp_connection", "test")) < 32:
            pytest.skip("serp_connection is not prepared")

    @pytest.mark.parametrize(
        "flow_folder",
        [
            SAMPLE_FLOW,
        ],
    )
    def test_executor_exec_bulk_with_timeout(self, flow_folder, dev_connections):
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections, raise_ex=True, line_timeout_sec=5)
        run_id = str(uuid.uuid4())
        bulk_inputs = self.get_bulk_inputs()
        nlines = len(bulk_inputs)
        bulk_results = executor.exec_bulk(bulk_inputs, run_id)
        assert isinstance(bulk_results, BulkResult)
        assert len(bulk_results.line_results) == nlines

        for i, line_result in enumerate(bulk_results.line_results):
            assert isinstance(line_result, LineResult)
            assert line_result.run_info.error["message"] == f"Line {i} execution timeout for exceeding 5 seconds"
            assert line_result.run_info.error["code"] == "UserError"
            assert line_result.run_info.status == Status.Failed

    @pytest.mark.parametrize(
        "flow_folder",
        [
            ONE_LINE_OF_BULK_TEST_TIMEOUT,
        ],
    )
    def test_executor_exec_bulk_with_one_line_timeout(self, flow_folder, dev_connections):
        mem_run_storage = MemoryRunStorage()
        executor = FlowExecutor.create(
            get_yaml_file(flow_folder), dev_connections, raise_ex=False, storage=mem_run_storage, line_timeout_sec=15
        )
        run_id = str(uuid.uuid4())
        bulk_inputs = self.get_bulk_inputs(flow_folder=flow_folder)
        nlines = len(bulk_inputs)
        bulk_results = executor.exec_bulk(bulk_inputs, run_id)
        assert isinstance(bulk_results, BulkResult)
        assert len(bulk_results.line_results) == nlines

        for line_result in bulk_results.line_results:
            flow_run_info = line_result.run_info
            msg = f"Flow run {flow_run_info.run_id} is not persisted in memory storage."
            assert flow_run_info.run_id in mem_run_storage._flow_runs, msg
            if flow_run_info.index == 2:
                assert (
                    flow_run_info.error["message"]
                    == f"Line {flow_run_info.index} execution timeout for exceeding 15 seconds"
                )
                assert flow_run_info.error["code"] == "UserError"
                assert flow_run_info.status == Status.Failed
            else:
                assert flow_run_info.status == Status.Completed
            for node_name, node_run_info in line_result.node_run_infos.items():
                msg = f"Node run {node_run_info.run_id} is not persisted in memory storage."
                assert node_run_info.run_id in mem_run_storage._node_runs, msg
                run_info_in_mem = mem_run_storage._node_runs[node_run_info.run_id]
                assert serialize(node_run_info) == serialize(run_info_in_mem)
                msg = f"Node run name {node_run_info.node} is not correct, expected {node_name}"
                assert mem_run_storage._node_runs[node_run_info.run_id].node == node_name
