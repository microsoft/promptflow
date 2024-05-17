# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path

from promptflow._constants import OutputsFolderName
from promptflow._utils.multimedia_utils import MultimediaProcessor
from promptflow.contracts.run_info import FlowRunInfo
from promptflow.contracts.run_info import RunInfo as NodeRunInfo
from promptflow.storage import AbstractRunStorage


class ServiceStorage(AbstractRunStorage):
    """This storage persist multimedia data after run info is put into the output queue."""

    def __init__(self, output_dir: Path):
        self._flow_outputs_path = output_dir / OutputsFolderName.FLOW_OUTPUTS
        self._flow_artifacts_path = output_dir / OutputsFolderName.FLOW_ARTIFACTS
        self._node_artifacts_path = output_dir / OutputsFolderName.NODE_ARTIFACTS

    def persist_node_run(self, run_info: NodeRunInfo):
        node_folder = self._node_artifacts_path / str(run_info.index) / run_info.node
        multimedia_processor = MultimediaProcessor.create(run_info.message_format)
        multimedia_processor.process_multimedia_in_run_info(run_info, node_folder)

    def persist_flow_run(self, run_info: FlowRunInfo):
        flow_folder = self._flow_artifacts_path / str(run_info.index)
        multimedia_processor = MultimediaProcessor.create(run_info.message_format)
        multimedia_processor.process_multimedia_in_run_info(run_info, flow_folder)
