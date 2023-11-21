import subprocess
from pathlib import Path
from typing import Any, Mapping, Optional

from promptflow.batch._base_executor_proxy import APIBasedExecutorProxy
from promptflow.executor._result import AggregationResult
from promptflow.storage._run_storage import AbstractRunStorage

EXECUTOR_DOMAIN = "http://localhost:"
EXECUTOR_PORT = 8080


class CSharpExecutorProxy(APIBasedExecutorProxy):
    def __init__(self, process: subprocess.Popen):
        self._process = process

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
        assembly_folder = working_dir / "bin/Debug/net6.0"
        dll_path = "D:/PromptflowCS/src/PromptflowCSharp/Promptflow.Service/bin/Debug/net6.0/Promptflow.Service.dll"
        command = f'dotnet {dll_path} -p {EXECUTOR_PORT} -y {flow_file} -a {assembly_folder} -c "" -l ""'
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

    @property
    def api_endpoint(self) -> str:
        return EXECUTOR_DOMAIN + str(EXECUTOR_PORT)

    async def exec_aggregation_async(
        self,
        batch_inputs: Mapping[str, Any],
        aggregation_inputs: Mapping[str, Any],
        run_id: Optional[str] = None,
    ) -> AggregationResult:
        return AggregationResult()

    @classmethod
    def generate_tool_metadata(cls, flow_dag: dict, working_dir: Path) -> dict:
        return {}
