# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from functools import partial
from pathlib import Path

from promptflow._utils.dataclass_serializer import serialize
from promptflow.contracts.multimedia import Image, PFBytes
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
            run_info.inputs = self._serialize(run_info.inputs)
        if run_info.output:
            run_info.output = self._serialize(run_info.output)

    def persist_flow_run(self, run_info: FlowRunInfo):
        if run_info.inputs:
            run_info.inputs = self._serialize(run_info.inputs)
        if run_info.output:
            run_info.output = self._serialize(run_info.output)

    def _serialize(self, value):
        if self._base_dir:
            pfbytes_file_reference_encoder = PFBytes.get_file_reference_encoder(
                folder_path=self._base_dir,
                relative_path=self._sub_dir
            )
        else:
            pfbytes_file_reference_encoder = None
        serialization_funcs = {Image: partial(Image.serialize, **{"encoder": pfbytes_file_reference_encoder})}
        return serialize(value, serialization_funcs=serialization_funcs)
