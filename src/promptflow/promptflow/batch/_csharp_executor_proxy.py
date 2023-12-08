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
from promptflow.executor._result import AggregationResult
from promptflow.storage._run_storage import AbstractRunStorage

EXECUTOR_SERVICE_DOMAIN = "http://localhost:"
EXECUTOR_SERVICE_DLL = "Promptflow.DotnetService.dll"


class CSharpExecutorProxy(APIBasedExecutorProxy):
    def __init__(self, process: subprocess.Popen, port: str):
        self._process = process
        self._port = port

    @property
    def api_endpoint(self) -> str:
        return EXECUTOR_SERVICE_DOMAIN + self._port

    @classmethod
    def create(
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
        command = [
            "dotnet",
            EXECUTOR_SERVICE_DLL,
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
        ]
        process = subprocess.Popen(command)
        return cls(process, port)

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
    def generate_tool_metadata(cls, working_dir: Path) -> dict:
        promptflow_folder = working_dir / PROMPT_FLOW_DIR_NAME
        if promptflow_folder.exists():
            with open(promptflow_folder / FLOW_TOOLS_JSON, mode="r", encoding=DEFAULT_ENCODING) as f:
                return json.load(f)
        return {}

    @classmethod
    def find_available_port(cls) -> str:
        """Find an available port on localhost"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            _, port = s.getsockname()
            return str(port)
