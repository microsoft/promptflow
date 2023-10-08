# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path

from promptflow._utils.dataclass_serializer import serialize
from promptflow.contracts.multimedia import PFBytes
from promptflow.contracts.run_info import FlowRunInfo
from promptflow.contracts.run_info import RunInfo as NodeRunInfo


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
    def __init__(self, working_dir: Path, output_dir: Path = None, intermediate_dir: Path = None):
        self._working_dir = working_dir
        self._output_dir = output_dir or Path(".promptflow/output")
        self._intermediate_dir = intermediate_dir or Path(".promptflow/intermediate")
        self._input_dir = Path(".promptflow/input")

    def persist_node_run(self, run_info: NodeRunInfo):
        if run_info.output:
            run_info.output = self._ensure_serializable(run_info.output, self._working_dir, self._intermediate_dir)
        if run_info.inputs:
            run_info.inputs = self._ensure_serializable(run_info.inputs, self._working_dir, self._input_dir)

    def persist_flow_run(self, run_info: FlowRunInfo):
        if run_info.output:
            run_info.output = self._ensure_serializable(run_info.output, self._working_dir, self._output_dir)
        if run_info.inputs:
            run_info.inputs = self._ensure_serializable(run_info.inputs, self._working_dir, self._input_dir)

    def _ensure_serializable(self, value: dict, folder_path: Path, relative_path : Path = None):
        pfbytes_file_reference_encoder = PFBytes.get_file_reference_encoder(
            folder_path=folder_path,
            relative_path=relative_path)
        return serialize(value, pfbytes_file_reference_encoder=pfbytes_file_reference_encoder)
