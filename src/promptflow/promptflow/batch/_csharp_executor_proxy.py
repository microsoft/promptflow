import asyncio
import datetime
import sys
from pathlib import Path
from typing import Any, Mapping, Optional

from promptflow._utils.context_utils import _change_working_dir
from promptflow.batch._base_executor_proxy import AbstractExecutorProxy
from promptflow.contracts.run_info import FlowRunInfo
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

    @classmethod
    def _dict_from_csharp(cls, csharp_dict):
        if csharp_dict is None:
            return None
        output = {}
        for key in csharp_dict.Keys:
            output[key] = csharp_dict[key]
        return output

    @classmethod
    def _datetime_from_csharp(cls, csharp_datetime):
        return datetime.datetime(
            csharp_datetime.Year,
            csharp_datetime.Month,
            csharp_datetime.Day,
            csharp_datetime.Hour,
            csharp_datetime.Minute,
            csharp_datetime.Second,
            # seems that microsecond is not supported in all versions of DotNet?
            # csharp_datetime.Microsecond,
        )

    def exec_line(
        self,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
    ) -> LineResult:
        from System import Object, String
        from System.Collections.Generic import Dictionary

        from Promptflow.Contracts.JsonSchema import ExecuteFlowRequest

        csharp_request = ExecuteFlowRequest()
        csharp_inputs = Dictionary[String, Object]()
        for key, value in inputs.items():
            csharp_inputs[key] = value
        csharp_request.Inputs = csharp_inputs
        csharp_request.LineNumber = index
        csharp_request.RunId = run_id
        task = self._executor.ExecuteAsync(csharp_request)
        task_result = task.Result

        return LineResult(
            output=self._dict_from_csharp(task_result.Output),
            aggregation_inputs=self._dict_from_csharp(task_result.AggregationInputs),
            node_run_infos={},
            run_info=FlowRunInfo(
                run_id=task_result.RunInfo.RunId,
                status=task_result.RunInfo.Status,
                error=task_result.RunInfo.Error,
                inputs=self._dict_from_csharp(task_result.RunInfo.Inputs),
                output=self._dict_from_csharp(task_result.RunInfo.Output),
                metrics=self._dict_from_csharp(task_result.RunInfo.Metrics),
                request=task_result.RunInfo.Request,
                parent_run_id=task_result.RunInfo.ParentRunId,
                root_run_id=task_result.RunInfo.RootRunId,
                source_run_id=task_result.RunInfo.SourceRunId,
                flow_id=task_result.RunInfo.FlowId,
                start_time=self._datetime_from_csharp(task_result.RunInfo.StartTime),
                end_time=self._datetime_from_csharp(task_result.RunInfo.EndTime),
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
