# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------


from pathlib import Path

from promptflow._constants import OutputsFolderName
from promptflow._utils.utils import prepare_folder
from promptflow.promptflow.contracts.run_info import FlowRunInfo
from promptflow.promptflow.contracts.run_info import RunInfo as NodeRunInfo
from promptflow.storage import AbstractRunStorage


class ExecutorServiceStorage(AbstractRunStorage):
    def __init__(self, root_dir: Path):
        # prepare folder ...
        prepare_folder(root_dir / OutputsFolderName.FLOW_OUTPUTS)
        prepare_folder(root_dir / OutputsFolderName.FLOW_ARTIFACTS)
        prepare_folder(root_dir / OutputsFolderName.NODE_ARTIFACTS)

    def persist_flow_run(self, run_info: FlowRunInfo):
        pass

    def persist_node_run(self, run_info: NodeRunInfo):
        pass
