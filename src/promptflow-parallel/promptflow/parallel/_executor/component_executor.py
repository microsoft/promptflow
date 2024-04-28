# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from promptflow.executor import FlowExecutor
from promptflow.parallel._config.model import ParallelRunConfig
from promptflow.parallel._executor.base import AbstractExecutor


class ComponentRunExecutor(AbstractExecutor):
    def _create_flow_executor(self, connections: dict, config: ParallelRunConfig) -> FlowExecutor:
        return FlowExecutor.create(
            self._flow_dag,
            connections,
            node_override=config.connections_override,
            raise_ex=True,
            storage=None,
        )
