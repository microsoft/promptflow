# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------


from functools import partial
from pathlib import Path

from promptflow._constants import OutputsFolderName
from promptflow._utils.multimedia_utils import _process_recursively, get_file_reference_encoder
from promptflow._utils.utils import prepare_folder
from promptflow.contracts.multimedia import Image
from promptflow.contracts.run_info import FlowRunInfo
from promptflow.contracts.run_info import RunInfo as NodeRunInfo
from promptflow.storage import AbstractRunStorage


class ExecutorServiceStorage(AbstractRunStorage):
    def __init__(self, output_dir: Path):
        self._flow_outputs_path = prepare_folder(output_dir / OutputsFolderName.FLOW_OUTPUTS)
        self._flow_artifacts_path = prepare_folder(output_dir / OutputsFolderName.FLOW_ARTIFACTS)
        self._node_artifacts_path = prepare_folder(output_dir / OutputsFolderName.NODE_ARTIFACTS)

    def persist_flow_run(self, run_info: FlowRunInfo):
        flow_folder = prepare_folder(self._flow_artifacts_path / run_info.index)
        self._process_multimedia_in_run_info(run_info, flow_folder)

    def persist_node_run(self, run_info: NodeRunInfo):
        node_folder = prepare_folder(self._node_artifacts_path / run_info.index / run_info.node)
        self._process_multimedia_in_run_info(run_info, node_folder)

    def _process_multimedia_in_run_info(self, run_info, folder_path):
        if run_info.inputs:
            run_info.inputs = self._serialize_multimedia(run_info.inputs, folder_path)
        if run_info.output:
            run_info.output = self._serialize_multimedia(run_info.output, folder_path)
            run_info.result = None
        if run_info.api_calls:
            run_info.api_calls = self._serialize_multimedia(run_info.api_calls, folder_path)

    def _serialize_multimedia(self, value, folder_path):
        pfbytes_file_reference_encoder = get_file_reference_encoder(folder_path=folder_path)
        serialization_funcs = {Image: partial(Image.serialize, **{"encoder": pfbytes_file_reference_encoder})}
        return _process_recursively(value, process_funcs=serialization_funcs)
