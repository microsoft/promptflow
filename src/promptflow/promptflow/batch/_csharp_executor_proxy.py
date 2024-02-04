# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
import os
import socket
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any, Mapping, Optional

from promptflow._core._errors import MetaFileNotFound, MetaFileReadError, UnexpectedError
from promptflow._sdk._constants import DEFAULT_ENCODING, FLOW_TOOLS_JSON, PROMPT_FLOW_DIR_NAME
from promptflow._utils.yaml_utils import dump_yaml
from promptflow.batch._base_executor_proxy import APIBasedExecutorProxy
from promptflow.executor._result import AggregationResult
from promptflow.storage._run_storage import AbstractRunStorage

EXECUTOR_SERVICE_DOMAIN = "http://localhost:"
EXECUTOR_SERVICE_DLL = "Promptflow.dll"


class CSharpExecutorProxy(APIBasedExecutorProxy):
    def __init__(
        self,
        *,
        process: subprocess.Popen,
        port: str,
        working_dir: Path,
        temp_dag_file: Optional[Path] = None,
        chat_output_name: Optional[str] = None,
    ):
        self._process = process
        self._port = port
        self._working_dir = working_dir
        self._temp_dag_file = temp_dag_file
        self.chat_output_name = chat_output_name

    @property
    def api_endpoint(self) -> str:
        return EXECUTOR_SERVICE_DOMAIN + self._port

    def _get_flow_meta(self) -> dict:
        # TODO: this should be got from flow.json for all languages by default?
        flow_meta_json_path = self._working_dir / ".promptflow" / "flow.json"
        if not flow_meta_json_path.is_file():
            raise MetaFileNotFound(
                message_format=(
                    # TODO: pf flow validate should be able to generate flow.json
                    "Failed to fetch meta of inputs: cannot find {file_path}, please retry."
                ),
                file_path=flow_meta_json_path.absolute().as_posix(),
            )

        with open(flow_meta_json_path, mode="r", encoding=DEFAULT_ENCODING) as flow_meta_json_path:
            return json.load(flow_meta_json_path)

    @classmethod
    def _generate_flow_meta(cls, flow_file: str, assembly_folder: Path):
        command = [
            "dotnet",
            EXECUTOR_SERVICE_DLL,
            "--flow_meta",
            "--yaml_path",
            flow_file,
            "--assembly_folder",
            ".",
        ]
        try:
            subprocess.check_output(
                command,
                cwd=assembly_folder,
            )
        except subprocess.CalledProcessError as e:
            raise UnexpectedError(
                message_format=f"Failed to generate flow meta for csharp flow.\n"
                f"Command: {' '.join(command)}\n"
                f"Working directory: {assembly_folder.as_posix()}\n"
                f"Return code: {e.returncode}\n"
                f"Output: {e.output}",
            )

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
        chat_output_name = kwargs.pop("chat_output_name", None)
        init_error_file = Path(working_dir) / f"init_error_{str(uuid.uuid4())}.json"
        init_error_file.touch()

        assembly_folder = flow_file.parent
        # TODO: should we change the interface to init the proxy (always pass entry for eager mode)?
        if "entry" in kwargs:
            fd, temp_dag_file = tempfile.mkstemp(suffix=".yaml", text=True)
            os.write(fd, dump_yaml({"entry": kwargs["entry"], "path": flow_file.as_posix()}).encode(DEFAULT_ENCODING))
            # need to close the fd manually, or it can't be used in subprocess
            os.close(fd)
            flow_file = Path(temp_dag_file)

            # generate flow meta
            cls._generate_flow_meta(
                flow_file=temp_dag_file,
                assembly_folder=assembly_folder,
            )
        else:
            temp_dag_file = None

        command = [
            "dotnet",
            EXECUTOR_SERVICE_DLL,
            "--execution_service",
            "--port",
            port,
            "--yaml_path",
            flow_file.as_posix(),
            "--assembly_folder",
            ".",
            "--log_path",
            log_path,
            "--log_level",
            "Warning",
            "--error_file_path",
            init_error_file,
        ]
        process = subprocess.Popen(command)
        executor_proxy = cls(
            process=process,
            port=port,
            temp_dag_file=temp_dag_file,
            working_dir=working_dir,
            chat_output_name=chat_output_name,
        )
        try:
            await executor_proxy.ensure_executor_startup(init_error_file)
        finally:
            Path(init_error_file).unlink()
        return executor_proxy

    async def destroy(self):
        """Destroy the executor"""
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
        if self._temp_dag_file and os.path.isfile(self._temp_dag_file):
            Path(self._temp_dag_file).unlink()

    async def exec_aggregation_async(
        self,
        batch_inputs: Mapping[str, Any],
        aggregation_inputs: Mapping[str, Any],
        run_id: Optional[str] = None,
    ) -> AggregationResult:
        return AggregationResult({}, {}, {})

    def _is_executor_active(self):
        """Check if the process is still running and return False if it has exited"""
        # get the exit code of the process by poll() and if it is None, it means the process is still running
        return self._process.poll() is None

    @classmethod
    def _get_tool_metadata(cls, flow_file: Path, working_dir: Path) -> dict:
        flow_tools_json_path = working_dir / PROMPT_FLOW_DIR_NAME / FLOW_TOOLS_JSON
        if flow_tools_json_path.is_file():
            with open(flow_tools_json_path, mode="r", encoding=DEFAULT_ENCODING) as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    raise MetaFileReadError(
                        message_format="Failed to fetch meta of tools: {file_path} is not a valid json file.",
                        file_path=flow_tools_json_path.absolute().as_posix(),
                    )
        raise MetaFileNotFound(
            message_format=(
                "Failed to fetch meta of tools: cannot find {file_path}, please build the flow project first."
            ),
            file_path=flow_tools_json_path.absolute().as_posix(),
        )

    @classmethod
    def find_available_port(cls) -> str:
        """Find an available port on localhost"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            _, port = s.getsockname()
            return str(port)
