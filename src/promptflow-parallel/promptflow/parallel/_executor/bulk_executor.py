# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path

from promptflow.executor import FlowExecutor
from promptflow.parallel._config.model import ParallelRunConfig
from promptflow.parallel._executor.base import AbstractExecutor
from promptflow.storage._run_storage import DummyRunStorage


class BulkRunExecutor(AbstractExecutor):
    def _create_flow_executor(self, connections: dict, config: ParallelRunConfig) -> FlowExecutor:
        return FlowExecutor.create(
            self._flow_dag,
            connections,
            node_override=config.connections_override,
            raise_ex=False,
            storage=DummyRunStorage() if config.is_debug_enabled else None,
        )

    def _resolve_working_dir(self) -> Path:
        return self._config.pf_model_dir or super()._resolve_working_dir()
