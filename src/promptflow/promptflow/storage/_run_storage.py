# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import uuid
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

from promptflow._utils.dataclass_serializer import serialize
from promptflow.contracts.multimedia import Image
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

    def persist_node_run(self, run_info: NodeRunInfo):
        self._persist_image(run_info.output, self._intermediate_dir, run_info.node)
        if run_info.output:
            run_info.output = serialize(run_info.output)
        if run_info.result:
            run_info.result = serialize(run_info.result)

    def persist_flow_run(self, run_info: FlowRunInfo):
        self._persist_image(run_info.output, self._output_dir)
        if run_info.output:
            run_info.output = serialize(run_info.output)
        if run_info.result:
            run_info.result = serialize(run_info.result)

    def _persist_image(self, output: Any, relative_path: Path, file_name_perfix: str = None):
        if isinstance(output, Image):
            name = f"{file_name_perfix}_{uuid.uuid4()}" if file_name_perfix else str(uuid.uuid4())
            output.save_to(name, self._working_dir, relative_path)
        elif isinstance(output, dict):
            for _, value in output.items():
                self._persist_image(value, relative_path, file_name_perfix)
        elif isinstance(output, list):
            for item in output:
                self._persist_image(item, relative_path, file_name_perfix)
        elif is_dataclass(output):
            for field in fields(output):
                self._persist_image(getattr(output, field.name), relative_path, file_name_perfix)
