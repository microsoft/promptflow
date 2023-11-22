import subprocess
from pathlib import Path
from typing import Any, Mapping, Optional

from promptflow.batch._base_executor_proxy import APIBasedExecutorProxy
from promptflow.executor._result import AggregationResult
from promptflow.storage._run_storage import AbstractRunStorage

EXECUTOR_DOMAIN = "http://localhost:"
EXECUTOR_PORT = "12306"
SERVICE_DLL = "Promptflow.Service.dll"


class CSharpExecutorProxy(APIBasedExecutorProxy):
    def __init__(self, process: subprocess.Popen):
        self._process = process

    @property
    def api_endpoint(self) -> str:
        return EXECUTOR_DOMAIN + EXECUTOR_PORT

    @classmethod
    def create(
        cls,
        flow_file: Path,
        working_dir: Optional[Path] = None,
        *,
        connections: Optional[dict] = None,
        storage: Optional[AbstractRunStorage] = None,
    ) -> "CSharpExecutorProxy":
        """Create a new executor"""
        command = f'dotnet {SERVICE_DLL} -p {EXECUTOR_PORT} -y {flow_file} -a "." -c "" -l ""'
        process = subprocess.Popen(command, shell=True)
        return cls(process)

    def destroy(self):
        """Destroy the executor"""
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()

    async def exec_aggregation_async(
        self,
        batch_inputs: Mapping[str, Any],
        aggregation_inputs: Mapping[str, Any],
        run_id: Optional[str] = None,
    ) -> AggregationResult:
        return AggregationResult({}, {}, {})

    @classmethod
    def generate_tool_metadata(cls, flow_dag: dict, working_dir: Path) -> dict:
        return {}
