# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from functools import partial
from pathlib import Path

from promptflow._utils.multimedia_utils import _process_recursively, get_file_reference_encoder
from promptflow.contracts.multimedia import Image, Text
from promptflow.contracts.run_info import FlowRunInfo
from promptflow.contracts.run_info import RunInfo as NodeRunInfo


class AbstractRunStorage:
    def persist_node_run(self, run_info: NodeRunInfo):
        """Write the node run info to somewhere immediately after the node is executed.

        :param run_info: The run info of the node.
        :type run_info: ~promptflow.contracts.run_info.RunInfo
        """
        raise NotImplementedError("AbstractRunStorage is an abstract class, no implementation for persist_node_run.")

    def persist_flow_run(self, run_info: FlowRunInfo):
        """Write the flow run info to somewhere immediately after one line data is executed for the flow.

        :param run_info: The run info of the node.
        :type run_info: ~promptflow.contracts.run_info.RunInfo
        """
        raise NotImplementedError("AbstractRunStorage is an abstract class, no implementation for persist_flow_run.")


class DummyRunStorage(AbstractRunStorage):
    def persist_node_run(self, run_info: NodeRunInfo):
        """Dummy implementation for persist_node_run

        :param run_info: The run info of the node.
        :type run_info: ~promptflow.contracts.run_info.RunInfo
        """
        pass

    def persist_flow_run(self, run_info: FlowRunInfo):
        """Dummy implementation for persist_flow_run

        :param run_info: The run info of the node.
        :type run_info: ~promptflow.contracts.run_info.RunInfo
        """
        pass


class DefaultRunStorage(AbstractRunStorage):
    def __init__(self, base_dir: Path = None, sub_dir: Path = None, version: int = None):
        """Initialize the default run storage.

        :param base_dir: The base directory to store the multimedia data.
        :type base_dir: Path
        :param sub_dir: The sub directory to store the multimedia data.
        :type sub_dir: Path
        """
        self._base_dir = base_dir
        self._sub_dir = sub_dir
        self._version = version if version is not None else 1

    @property
    def version(self):
        return self._version

    @version.setter
    def version(self, value):
        self._version = value

    def persist_node_run(self, run_info: NodeRunInfo):
        """Persist the multimedia data in node run info after the node is executed.

        :param run_info: The run info of the node.
        :type run_info: ~promptflow.contracts.run_info.RunInfo
        """
        if run_info.inputs:
            run_info.inputs = self._persist_images(run_info.inputs)
        if run_info.output:
            serialized_output = self._persist_images(run_info.output)
            run_info.output = serialized_output
            run_info.result = serialized_output
        if run_info.api_calls:
            run_info.api_calls = self._persist_images(run_info.api_calls)

    def persist_flow_run(self, run_info: FlowRunInfo):
        """Persist the multimedia data in flow run info after one line data is executed for the flow.

        :param run_info: The run info of the flow.
        :type run_info: ~promptflow.contracts.run_info.FlowRunInfo
        """
        if run_info.inputs:
            run_info.inputs = self._persist_images(run_info.inputs)
        if run_info.output:
            serialized_output = self._persist_images(run_info.output)
            run_info.output = serialized_output
            run_info.result = serialized_output
        if run_info.api_calls:
            run_info.api_calls = self._persist_images(run_info.api_calls)

    def _persist_images(self, value):
        """Serialize the images in the value to file path and save them to the disk.

        :param value: A value that may contain images.
        :type value: Any
        """
        if self._base_dir:
            pfbytes_file_reference_encoder = get_file_reference_encoder(
                folder_path=self._base_dir,
                relative_path=self._sub_dir,
                version=self._version,
            )
        else:
            pfbytes_file_reference_encoder = None
        serialization_funcs = {
            Image: partial(Image.serialize, **{"encoder": pfbytes_file_reference_encoder}), Text: Text.serialize
        }
        return _process_recursively(value, process_funcs=serialization_funcs)
