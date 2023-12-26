# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
import socket
import subprocess
from pathlib import Path
from typing import Any, Mapping, Optional

from promptflow._sdk._constants import DEFAULT_ENCODING, FLOW_TOOLS_JSON, PROMPT_FLOW_DIR_NAME
from promptflow.batch._base_executor_proxy import APIBasedExecutorProxy
from promptflow.batch._errors import ExecutorServiceUnhealthy
from promptflow.executor._result import AggregationResult
from promptflow.storage._run_storage import AbstractRunStorage

EXECUTOR_SERVICE_DOMAIN = "http://localhost:"
EXECUTOR_SERVICE_DLL = "Promptflow.dll"
EXECUTOR_INIT_ERROR_FILE = "init_error.json"


class CSharpExecutorProxy(APIBasedExecutorProxy):
    def __init__(self, process: subprocess.Popen, port: str):
        self._process = process
        self._port = port

    @property
    def api_endpoint(self) -> str:
        return EXECUTOR_SERVICE_DOMAIN + self._port

    @classmethod
    async def create(
        cls,
        flow_file: Path,
        working_dir: Optional[Path] = None,
        *,
        connections: Optional[dict] = None,
        storage: Optional[AbstractRunStorage] = None,
        **kwargs,
    ) -> "CSharpExecutorProxy":
        """Create a new executor"""
        port = cls.find_available_port()
        log_path = kwargs.get("log_path", "")
        init_error_file = Path(working_dir) / EXECUTOR_INIT_ERROR_FILE
        init_error_file.touch()
        command = [
            "dotnet",
            EXECUTOR_SERVICE_DLL,
            "-e",
            "-p",
            port,
            "--yaml_path",
            flow_file,
            "--assembly_folder",
            ".",
            "--log_path",
            log_path,
            "--log_level",
            "Warning",
            "--init_error_file",
            EXECUTOR_INIT_ERROR_FILE,
        ]
        process = subprocess.Popen(command)
        csharp_executor_proxy = cls(process, port)
        try:
            await csharp_executor_proxy.ensure_executor_health()
        except ExecutorServiceUnhealthy as ex:
            # raise the init error if there is any
            init_ex = cls.check_startup_error_from_file(init_error_file)
            raise init_ex or ex
        return csharp_executor_proxy

    async def destroy(self):
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
    def _get_tool_metadata(cls, flow_file: Path, working_dir: Path) -> dict:
        flow_tools_json_path = working_dir / PROMPT_FLOW_DIR_NAME / FLOW_TOOLS_JSON
        if flow_tools_json_path.is_file():
            with open(flow_tools_json_path, mode="r", encoding=DEFAULT_ENCODING) as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    raise RuntimeError(
                        f"Failed to fetch meta of tools: {flow_tools_json_path.absolute().as_posix()} "
                        f"is not a valid json file."
                    )
        raise FileNotFoundError(
            f"Failed to fetch meta of tools: cannot find {flow_tools_json_path.absolute().as_posix()}, "
            f"please build the flow project first."
        )

    @classmethod
    def find_available_port(cls) -> str:
        """Find an available port on localhost"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            _, port = s.getsockname()
            return str(port)
