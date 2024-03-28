import datetime
import json
import os
import shutil

import pytest

from promptflow._sdk.entities._run import Run
from promptflow._sdk.operations._local_storage_operations import LocalStorageOperations
from promptflow._utils.multimedia_utils import BasicMultimediaProcessor
from promptflow.contracts.multimedia import Image
from promptflow.contracts.run_info import FlowRunInfo, RunInfo, Status


def _clear_folder_contents(folder_path):
    for item in os.listdir(folder_path):
        item_path = os.path.join(folder_path, item)
        if os.path.isfile(item_path) or os.path.islink(item_path):
            os.unlink(item_path)
        elif os.path.isdir(item_path):
            shutil.rmtree(item_path)
    print(f"All contents of the folder '{folder_path}' have been removed.")


@pytest.fixture
def run_instance():
    return Run(flow="flow", name="run_name")


@pytest.fixture
def local_storage(run_instance):
    return LocalStorageOperations(run_instance)


@pytest.fixture
def node_run_info():
    return RunInfo(
        node="node1",
        flow_run_id="flow_run_id",
        run_id="run_id",
        status=Status.Completed,
        inputs={"image1": BasicMultimediaProcessor().create_image({"data:image/png;base64": "R0lGODlhAQABAAAAACw="})},
        output={"output1": BasicMultimediaProcessor().create_image({"data:image/png;base64": "R0lGODlhAQABAAAAACw="})},
        metrics={},
        error={},
        parent_run_id="parent_run_id",
        start_time=datetime.datetime.now(),
        end_time=datetime.datetime.now() + datetime.timedelta(seconds=5),
        index=1,
    )


@pytest.fixture
def flow_run_info():
    return FlowRunInfo(
        run_id="run_id",
        status=Status.Completed,
        error=None,
        inputs={"image1": BasicMultimediaProcessor().create_image({"data:image/png;base64": "R0lGODlhAQABAAAAACw="})},
        output={"output1": BasicMultimediaProcessor().create_image({"data:image/png;base64": "R0lGODlhAQABAAAAACw="})},
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


@pytest.mark.unittest
class TestLocalStorageOperations:
    def test_persist_node_run(self, local_storage, node_run_info):
        _clear_folder_contents(local_storage.path)
        local_storage.persist_node_run(node_run_info)
        expected_file_path = local_storage.path / "node_artifacts" / node_run_info.node / "000000001.jsonl"
        assert expected_file_path.exists()
        with open(expected_file_path, "r") as file:
            content = file.read()
            node_run_info_dict = json.loads(content)
            assert node_run_info_dict["NodeName"] == node_run_info.node
            assert node_run_info_dict["line_number"] == node_run_info.index

    def test_persist_flow_run(self, local_storage, flow_run_info):
        _clear_folder_contents(local_storage.path)
        local_storage.persist_flow_run(flow_run_info)
        expected_file_path = local_storage.path / "flow_artifacts" / "000000001_000000001.jsonl"
        assert expected_file_path.exists()
        with open(expected_file_path, "r") as file:
            content = file.read()
            flow_run_info_dict = json.loads(content)
            assert flow_run_info_dict["run_info"]["run_id"] == flow_run_info.run_id
            assert flow_run_info_dict["line_number"] == flow_run_info.index

    def test_load_node_run_info(self, local_storage, node_run_info):
        _clear_folder_contents(local_storage.path)
        assert local_storage.load_node_run_info_for_line(1) == []

        local_storage.persist_node_run(node_run_info)
        loaded_node_run_info = local_storage.load_node_run_info_for_line(1)

        assert len(loaded_node_run_info) == 1
        assert isinstance(loaded_node_run_info[0], RunInfo)
        assert loaded_node_run_info[0].node == node_run_info.node
        assert loaded_node_run_info[0].index == node_run_info.index
        assert isinstance(loaded_node_run_info[0].inputs["image1"], Image)
        assert isinstance(loaded_node_run_info[0].output["output1"], Image)

        assert local_storage.load_node_run_info_for_line(2) == []

    def test_load_flow_run_info(self, local_storage, flow_run_info):
        _clear_folder_contents(local_storage.path)
        assert local_storage.load_flow_run_info(1) is None

        local_storage.persist_flow_run(flow_run_info)
        loaded_flow_run_info = local_storage.load_flow_run_info(1)

        assert isinstance(loaded_flow_run_info, FlowRunInfo)
        assert loaded_flow_run_info.run_id == flow_run_info.run_id
        assert loaded_flow_run_info.status == flow_run_info.status
        assert isinstance(loaded_flow_run_info.inputs["image1"], Image)
        assert isinstance(loaded_flow_run_info.output["output1"], Image)

        assert local_storage.load_flow_run_info(2) is None
