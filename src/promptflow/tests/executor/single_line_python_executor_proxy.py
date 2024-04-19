# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path
from typing import Any, Mapping, Optional

from promptflow._proxy._base_executor_proxy import AbstractExecutorProxy
from promptflow.executor import FlowExecutor
from promptflow.executor._line_execution_process_pool import LineExecutionProcessPool
from promptflow.executor._result import LineResult
from promptflow.storage._run_storage import AbstractRunStorage


class SingleLinePythonExecutorProxy(AbstractExecutorProxy):
    def __init__(self, flow_executor: FlowExecutor, line_execution_process_pool: LineExecutionProcessPool):
        """This is a temporary solution of PythonExecutorProxy to support exec batch run line by line for test purpose.
        A formal version of PythonExecutorProxy will replace this one.
        :param flow_executor: flow executor
        :type flow_executor: FlowExecutor
        :param line_execution_process_pool: line execution process pool
        :type line_execution_process_pool: LineExecutionProcessPool
        """
        super().__init__()
        self._flow_executor = flow_executor
        self._line_execution_process_pool = line_execution_process_pool

    @classmethod
    async def create(
        cls,
        flow_file: Path,
        working_dir: Optional[Path] = None,
        *,
        connections: Optional[dict] = None,
        storage: Optional[AbstractRunStorage] = None,
        output_dir: Optional[Path] = None,
        run_id: Optional[str] = None,
        **kwargs,
    ) -> "SingleLinePythonExecutorProxy":

        flow_executor = FlowExecutor.create(flow_file, connections, working_dir, storage=storage, raise_ex=False)
        line_execution_process_pool = LineExecutionProcessPool(output_dir, flow_executor, run_id=run_id)
        line_execution_process_pool.start()
        return cls(flow_executor, line_execution_process_pool)

    async def exec_line_async(
        self,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
    ) -> LineResult:
        return await self._line_execution_process_pool.submit(run_id, index, inputs)

    async def destroy(self):
        self._line_execution_process_pool.close()
