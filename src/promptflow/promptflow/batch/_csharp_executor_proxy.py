# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
import socket
import subprocess
from pathlib import Path
from typing import Any, Mapping, Optional

from promptflow._constants import LINE_NUMBER_KEY
from promptflow._sdk._constants import DEFAULT_ENCODING, FLOW_TOOLS_JSON, PROMPT_FLOW_DIR_NAME
from promptflow.batch._base_executor_proxy import APIBasedExecutorProxy
from promptflow.executor._result import AggregationResult, LineResult
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

    async def exec_line_async(
        self,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
    ) -> LineResult:
        line_result = await super().exec_line_async(inputs, index, run_id)
        # TODO: check if we should ask C# executor to keep unmatched inputs, although it's not so straightforward
        #   for executor service to do so.
        # local_storage_operations.load_inputs_and_outputs now have an assumption that there is an extra
        # line_number key in the inputs.
        # This key will be appended to the inputs in below call stack:
        # BatchEngine.run =>
        # BatchInputsProcessor.process_batch_inputs =>
        # ... =>
        # BatchInputsProcessor._merge_input_dicts_by_line
        # For python, it will be kept in the returned line_result.run_info.inputs
        # For csharp, it will be dropped by executor service for now
        # Append it here for now to make behavior consistent among ExecutorProxy.
        line_result.run_info.inputs[LINE_NUMBER_KEY] = index
        return line_result

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
