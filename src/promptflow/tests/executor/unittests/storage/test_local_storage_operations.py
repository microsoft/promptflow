import datetime
import json
from pathlib import Path

import pytest

from promptflow._sdk.entities._run import Run
from promptflow._sdk.operations._local_storage_operations import LocalStorageOperations
from promptflow.contracts.run_info import FlowRunInfo, RunInfo, Status


@pytest.mark.unittest
class TestLocalStorageOperations:
    def get_node_run_info_example(self):
        return RunInfo(
            node="node1",
            flow_run_id="flow_run_id",
            run_id="run_id",
            status=Status.Completed,
            inputs={"image1": {"data:image/png;path": "test.png"}},
            output={"output1": {"data:image/png;path": "test.png"}},
            metrics={},
            error={},
            parent_run_id="parent_run_id",
            start_time=datetime.datetime.now(),
            end_time=datetime.datetime.now() + datetime.timedelta(seconds=5),
            index=1,
        )

    def get_flow_run_info_example(self):
        return FlowRunInfo(
            run_id="run_id",
            status=Status.Completed,
            error=None,
            inputs={"image1": {"data:image/png;path": "test.png"}},
            output={"output1": {"data:image/png;path": "test.png"}},
            metrics={},
            request="request",
            parent_run_id="parent_run_id",
            root_run_id="root_run_id",
            source_run_id="source_run_id",
            flow_id="flow_id",
            start_time=datetime.datetime.now(),
            end_time=datetime.datetime.now() + datetime.timedelta(seconds=5),
            index=1,
        )

    def test_persist_node_run(self):
        run_instance = Run(flow="flow", name="run_name")
        local_storage = LocalStorageOperations(run_instance)
        node_run_info = self.get_node_run_info_example()
        local_storage.persist_node_run(node_run_info)
        expected_file_path = local_storage.path / "node_artifacts" / node_run_info.node / "000000001.jsonl"
        assert expected_file_path.exists()
        with open(expected_file_path, "r") as file:
            content = file.read()
            node_run_info_dict = json.loads(content)
            assert node_run_info_dict["NodeName"] == node_run_info.node
            assert node_run_info_dict["line_number"] == node_run_info.index

    def test_persist_flow_run(self):
        run_instance = Run(flow="flow", name="run_name")
        local_storage = LocalStorageOperations(run_instance)
        flow_run_info = self.get_flow_run_info_example()
        local_storage.persist_flow_run(flow_run_info)
        expected_file_path = local_storage.path / "flow_artifacts" / "000000001_000000001.jsonl"
        assert expected_file_path.exists()
        with open(expected_file_path, "r") as file:
            content = file.read()
            flow_run_info_dict = json.loads(content)
            assert flow_run_info_dict["run_info"]["run_id"] == flow_run_info.run_id
            assert flow_run_info_dict["line_number"] == flow_run_info.index

    def test_load_node_run_info(self):
        run_instance = Run(flow="flow_load", name="flow_load_run_name")
        local_storage = LocalStorageOperations(run_instance)
        node_run_info = self.get_node_run_info_example()
        local_storage.persist_node_run(node_run_info)

        loaded_node_run_info = local_storage.load_all_node_run_info()
        print(loaded_node_run_info)
        assert len(loaded_node_run_info) == 1
        assert loaded_node_run_info[0]["node"] == node_run_info.node
        assert loaded_node_run_info[0]["index"] == node_run_info.index
        assert loaded_node_run_info[0]["inputs"]["image1"]["data:image/png;path"] == str(
            Path(local_storage._node_infos_folder, node_run_info.node, "test.png")
        )
        assert loaded_node_run_info[0]["output"]["output1"]["data:image/png;path"] == str(
            Path(local_storage._node_infos_folder, node_run_info.node, "test.png")
        )

        res = local_storage.load_node_run_info_for_line(1)
        assert isinstance(res["node1"], RunInfo)
        assert res["node1"].node == node_run_info.node

    def test_load_flow_run_info(self):
        run_instance = Run(flow="flow_load", name="flow_load_run_name")
        local_storage = LocalStorageOperations(run_instance)
        flow_run_info = self.get_flow_run_info_example()
        local_storage.persist_flow_run(flow_run_info)

        loaded_flow_run_info = local_storage.load_all_flow_run_info()
        assert len(loaded_flow_run_info) == 1
        assert loaded_flow_run_info[0]["run_id"] == flow_run_info.run_id
        assert loaded_flow_run_info[0]["status"] == flow_run_info.status.value
        assert loaded_flow_run_info[0]["inputs"]["image1"]["data:image/png;path"] == str(
            Path(local_storage._run_infos_folder, "test.png")
        )
        assert loaded_flow_run_info[0]["output"]["output1"]["data:image/png;path"] == str(
            Path(local_storage._run_infos_folder, "test.png")
        )

        res = local_storage.load_flow_run_info(1)
        assert isinstance(res, FlowRunInfo)
        assert res.run_id == flow_run_info.run_id
