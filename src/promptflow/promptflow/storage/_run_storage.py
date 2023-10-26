# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from functools import partial
from pathlib import Path

from promptflow._utils.multimedia_utils import get_file_reference_encoder, recursive_process
from promptflow.contracts.multimedia import Image
from promptflow.contracts.run_info import FlowRunInfo, RunInfo as NodeRunInfo


class AbstractRunStorage:
    def persist_node_run(self, run_info: NodeRunInfo):
        """Write the node run info to somewhere immediately after the node is executed."""
        raise NotImplementedError("AbstractRunStorage is an abstract class, no implementation for persist_node_run.")

    def persist_flow_run(self, run_info: FlowRunInfo):
        """Write the flow run info to somewhere immediately after one line data is executed for the flow."""
        raise NotImplementedError("AbstractRunStorage is an abstract class, no implementation for persist_flow_run.")


class DummyRunStorage(AbstractRunStorage):
    def persist_node_run(self, run_info: NodeRunInfo):
        pass

    def persist_flow_run(self, run_info: FlowRunInfo):
        pass


class DefaultRunStorage(AbstractRunStorage):
    def __init__(self, base_dir: Path = None, sub_dir: Path = None):
        self._base_dir = base_dir
        self._sub_dir = sub_dir

    def persist_node_run(self, run_info: NodeRunInfo):
        if run_info.inputs:
            run_info.inputs = self._persist_images(run_info.inputs)
        if run_info.output:
            serialized_output = self._persist_images(run_info.output)
            run_info.output = serialized_output
            run_info.result = serialized_output
        if run_info.api_calls:
            run_info.api_calls = self._persist_images(run_info.api_calls)

    def persist_flow_run(self, run_info: FlowRunInfo):
        if run_info.inputs:
            run_info.inputs = self._persist_images(run_info.inputs)
        if run_info.output:
            serialized_output = self._persist_images(run_info.output)
            run_info.output = serialized_output
            run_info.result = serialized_output
        if run_info.api_calls:
            run_info.api_calls = self._persist_images(run_info.api_calls)

    def _persist_images(self, value):
        if self._base_dir:
            pfbytes_file_reference_encoder = get_file_reference_encoder(
                folder_path=self._base_dir,
                relative_path=self._sub_dir
            )
        else:
            pfbytes_file_reference_encoder = None
        serialization_funcs = {Image: partial(Image.serialize, **{"encoder": pfbytes_file_reference_encoder})}
        return recursive_process(value, process_funcs=serialization_funcs)
