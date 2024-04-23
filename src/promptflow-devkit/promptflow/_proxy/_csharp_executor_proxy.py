# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
import logging
import platform
import signal
import socket
import subprocess
import uuid
from pathlib import Path
from typing import NoReturn, Optional

from promptflow._sdk._constants import FLOW_META_JSON, PROMPT_FLOW_DIR_NAME, OSType
from promptflow._utils.flow_utils import is_flex_flow as is_flex_flow_func
from promptflow._utils.flow_utils import read_json_content
from promptflow.exceptions import UserErrorException
from promptflow.storage._run_storage import AbstractRunStorage

from ._csharp_base_executor_proxy import CSharpBaseExecutorProxy

EXECUTOR_SERVICE_DOMAIN = "http://localhost:"
EXECUTOR_SERVICE_DLL = "Promptflow.dll"


class CSharpExecutorProxy(CSharpBaseExecutorProxy):
    def __init__(
        self,
        *,
        process: subprocess.Popen,
        port: str,
        working_dir: Optional[Path] = None,
        enable_stream_output: bool = False,
        is_flex_flow: bool = False,
    ):
        self._process = process
        self._port = port
        self._is_flex_flow = is_flex_flow
        super().__init__(
            working_dir=working_dir,
            enable_stream_output=enable_stream_output,
        )

    @property
    def api_endpoint(self) -> str:
        return EXECUTOR_SERVICE_DOMAIN + self.port

    @property
    def port(self) -> str:
        return str(self._port)

    @classmethod
    def dump_metadata(cls, flow_file: Path, working_dir: Path) -> NoReturn:
        """In csharp, we need to generate metadata based on a dotnet command for now and the metadata will
        always be dumped.
        """
        command = [
            "dotnet",
            EXECUTOR_SERVICE_DLL,
            "--flow_meta",
            "--yaml_path",
            flow_file.absolute().as_posix(),
            "--assembly_folder",
            ".",
        ]
        try:
            subprocess.check_output(
                command,
                cwd=working_dir,
            )
        except subprocess.CalledProcessError as e:
            raise UserErrorException(
                message_format="Failed to generate flow meta for csharp flow.\n"
                "Command: {command}\n"
                "Working directory: {working_directory}\n"
                "Return code: {return_code}\n"
                "Output: {output}",
                command=" ".join(command),
                working_directory=working_dir.as_posix(),
                return_code=e.returncode,
                output=e.output,
            )

    def _get_interface_definition(self):
        if not self._is_flex_flow:
            return super()._get_interface_definition()
        flow_json_path = self.working_dir / PROMPT_FLOW_DIR_NAME / FLOW_META_JSON
        signatures = read_json_content(flow_json_path, "meta of tools")
        for key in set(signatures.keys()) - {"inputs", "outputs", "init"}:
            signatures.pop(key)
        return signatures

    @classmethod
    async def create(
        cls,
        flow_file: Path,
        working_dir: Optional[Path] = None,
        *,
        connections: Optional[dict] = None,
        storage: Optional[AbstractRunStorage] = None,
        init_kwargs: Optional[dict] = None,
        logging_level: int = logging.WARN,
        **kwargs,
    ) -> "CSharpExecutorProxy":
        """Create a new executor"""
        port = kwargs.get("port", None)
        log_path = kwargs.get("log_path", "")
        target_uuid = str(uuid.uuid4())
        init_error_file = Path(working_dir) / f"init_error_{target_uuid}.json"
        init_error_file.touch()
        if init_kwargs:
            init_kwargs_path = Path(working_dir) / f"init_kwargs_{target_uuid}.json"
            # TODO: complicated init_kwargs handling
            init_kwargs_path.write_text(json.dumps(init_kwargs))
        else:
            init_kwargs_path = None

        if port is None:
            # if port is not provided, find an available port and start a new execution service
            port = cls.find_available_port()

            if logging_level == logging.WARN:
                logging_level = "Warning"
            elif logging_level == logging.INFO:
                logging_level = "Information"
            elif logging_level == logging.DEBUG:
                logging_level = "Debug"
            elif logging_level == logging.ERROR:
                logging_level = "Error"
            elif logging_level == logging.CRITICAL:
                logging_level = "Fatal"
            else:
                logging_level = "Verbose"

            process = subprocess.Popen(
                cls._construct_service_startup_command(
                    port=port,
                    log_path=log_path,
                    log_level=logging_level,
                    error_file_path=init_error_file,
                    yaml_path=flow_file.as_posix(),
                    init_kwargs_path=init_kwargs_path.absolute().as_posix() if init_kwargs_path else None,
                ),
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if platform.system() == OSType.WINDOWS else 0,
            )
        else:
            # if port is provided, assume the execution service is already started
            process = None

        executor_proxy = cls(
            process=process,
            port=port,
            working_dir=working_dir,
            is_flex_flow=is_flex_flow_func(flow_path=flow_file, working_dir=working_dir),
            enable_stream_output=kwargs.get("enable_stream_output", False),
        )
        try:
            await executor_proxy.ensure_executor_startup(init_error_file)
        finally:
            Path(init_error_file).unlink()
            if init_kwargs_path:
                init_kwargs_path.unlink()
        return executor_proxy

    async def destroy(self):
        """Destroy the executor service.

        client.stream api in exec_line function won't pass all response one time.
        For API-based streaming chat flow, if executor proxy is destroyed, it will kill service process
        and connection will close. this will result in subsequent getting generator content failed.

        Besides, external caller usually wait for the destruction of executor proxy before it can continue and iterate
        the generator content, so we can't keep waiting here.

        On the other hand, the subprocess for execution service is not started in detach mode;
        it wll exit when parent process exit. So we simply skip the destruction here.
        """
        # process is not None, it means the executor service is started by the current executor proxy
        # and should be terminated when the executor proxy is destroyed if the service is still active
        if self._process and self._is_executor_active():
            if platform.system() == OSType.WINDOWS:
                # send CTRL_C_EVENT to the process to gracefully terminate the service
                self._process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                # for Linux and MacOS, Popen.terminate() will send SIGTERM to the process
                self._process.terminate()

            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                # TODO: pf.test won't work for streaming. Response will be fully consumed outside TestSubmitter context.
                #   We will still kill this process in case this is a true timeout but raise an error to indicate that
                #   we may meet runtime error when trying to consume the result.
                if not await self._all_generators_exhausted():
                    raise UserErrorException(
                        message_format="The executor service is still handling a stream request "
                        "whose response is not fully consumed yet."
                    )

    def _is_executor_active(self):
        """Check if the process is still running and return False if it has exited"""
        # if prot is provided on creation, assume the execution service is already started and keeps active within
        # the lifetime of current executor proxy
        if self._process is None:
            return True

        # get the exit code of the process by poll() and if it is None, it means the process is still running
        return self._process.poll() is None

    @classmethod
    def find_available_port(cls) -> str:
        """Find an available port on localhost"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            _, port = s.getsockname()
            return str(port)
