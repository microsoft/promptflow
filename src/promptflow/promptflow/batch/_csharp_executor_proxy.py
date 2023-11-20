import asyncio
import datetime
import sys
from pathlib import Path
from typing import Any, Mapping, Optional

from promptflow._utils.context_utils import _change_working_dir
from promptflow.batch._base_executor_proxy import AbstractExecutorProxy
from promptflow.contracts.run_info import FlowRunInfo, Status
from promptflow.executor._result import AggregationResult, LineResult
from promptflow.storage._run_storage import AbstractRunStorage


class CsharpExecutorProxy(AbstractExecutorProxy):
    def __init__(self, executor):
        self._executor = executor

    @classmethod
    def create(
        cls,
        flow_file: Path,
        working_dir: Optional[Path] = None,
        *,
        connections: Optional[dict] = None,
        storage: Optional[AbstractRunStorage] = None,
    ) -> "AbstractExecutorProxy":
        """Create a new executor"""
        working_dir = working_dir or flow_file.parent

        from pythonnet import load

        # pythonnet.load must be called before import clr
        load("coreclr")
        import clr

        with _change_working_dir(working_dir):
            sys.path.append(working_dir.as_posix())
            clr.AddReference("Promptflow")
            sys.path.pop()
            from Promptflow.Executor import YamlExecutor

            connection_provider_url = ""
            executor = YamlExecutor(
                flow_file.read_text(encoding="utf-8"), connection_provider_url, working_dir.as_posix()
            )
            return cls(executor)

    def destroy(self):
        """Destroy the executor"""
        pass

    def exec_line(
        self,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
    ) -> LineResult:
        start_time = datetime.datetime.now()
        from System import Object, String
        from System.Collections.Generic import Dictionary

        csharp_inputs = Dictionary[String, Object]()
        for key, value in inputs.items():
            csharp_inputs[key] = value
        task = self._executor.ExecuteAsync(csharp_inputs)
        task_result = task.Result

        output = {}
        for key in task_result.Keys:
            output[key] = task_result[key]
        return LineResult(
            output=output,
            aggregation_inputs={},
            node_run_infos={},
            run_info=FlowRunInfo(
                run_id="test",
                status=Status.Completed,
                error={},
                inputs=inputs,
                output=output,
                metrics={},
                request=None,
                parent_run_id="test",
                root_run_id="test",
                source_run_id="test",
                flow_id="test",
                start_time=start_time,
                end_time=datetime.datetime.now(),
            ),
        )

    async def exec_line_async(
        self,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
    ) -> LineResult:
        """Execute a line"""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self.exec_line, inputs, index, run_id)
        return result

    async def exec_aggregation_async(
        self,
        batch_inputs: Mapping[str, Any],
        aggregation_inputs: Mapping[str, Any],
        run_id: Optional[str] = None,
    ) -> AggregationResult:
        return AggregationResult(output={}, metrics={}, node_run_infos={})

    @classmethod
    def generate_tool_metadata(cls, flow_dag: dict, working_dir: Path) -> dict:
        return {}
