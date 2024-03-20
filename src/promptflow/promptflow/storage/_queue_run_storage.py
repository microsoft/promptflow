# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from multiprocessing import Queue
from pathlib import Path

from promptflow._constants import OutputsFolderName
from promptflow._utils.multimedia_utils import process_multimedia_in_run_info
from promptflow.contracts.run_info import FlowRunInfo
from promptflow.contracts.run_info import RunInfo as NodeRunInfo
from promptflow.storage import AbstractRunStorage


class QueueRunStorage(AbstractRunStorage):
    """This storage is used in line_execution_process_pool, where the run infos are put into the
    output queue when the flow is executed, and waiting for the monitoring thread to process it.
    """

    def __init__(self, queue: Queue):
        self.queue = queue

    def persist_node_run(self, run_info: NodeRunInfo):
        self.queue.put(run_info)

    def persist_flow_run(self, run_info: FlowRunInfo):
        self.queue.put(run_info)


class ServiceQueueRunStorage(QueueRunStorage):
    """This storage persist multimedia data after run info is put into the output queue."""

    def __init__(self, queue: Queue, output_dir: Path):
        super().__init__(queue)
        self._flow_outputs_path = output_dir / OutputsFolderName.FLOW_OUTPUTS
        self._flow_artifacts_path = output_dir / OutputsFolderName.FLOW_ARTIFACTS
        self._node_artifacts_path = output_dir / OutputsFolderName.NODE_ARTIFACTS

    def persist_node_run(self, run_info: NodeRunInfo):
        super().persist_node_run(run_info)
        node_folder = self._node_artifacts_path / str(run_info.index) / run_info.node
        process_multimedia_in_run_info(run_info, node_folder)

    def persist_flow_run(self, run_info: FlowRunInfo):
        super().persist_flow_run(run_info)
        flow_folder = self._flow_artifacts_path / str(run_info.index)
        process_multimedia_in_run_info(run_info, flow_folder)
