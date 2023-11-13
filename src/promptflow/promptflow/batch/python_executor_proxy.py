from pathlib import Path
from typing import Optional

from promptflow.batch.base_executor_proxy import AbstractExecutorProxy
from promptflow.executor import FlowExecutor
from promptflow.executor._result import LineResult
from promptflow.storage._run_storage import AbstractRunStorage


class PythonExecutorProxy(AbstractExecutorProxy):
    def __init__(self, executor: FlowExecutor):
        self._executor = executor

    @classmethod
    def create(
        cls,
        flow_file: Path,
        working_dir: Optional[Path] = None,
        *,
        connections: Optional[dict] = None,
        storage: Optional[AbstractRunStorage] = None
    ) -> "PythonExecutorProxy":
        flow_executor = FlowExecutor.create(flow_file, connections, working_dir, storage=storage)
        return cls(flow_executor)

    def exec_line(self, inputs, index, run_id) -> LineResult:
        return self._executor.exec_line(inputs, index, run_id=run_id)

    def exec_batch():
        pass

    def exec_aggregation():
        pass
