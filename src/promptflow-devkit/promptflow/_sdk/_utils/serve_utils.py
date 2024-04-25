import abc
import logging
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import webbrowser
from pathlib import Path
from typing import Any, Dict

from promptflow._constants import FlowLanguage
from promptflow._proxy._csharp_inspector_proxy import EXECUTOR_SERVICE_DLL
from promptflow._utils.flow_utils import resolve_flow_language, resolve_flow_path

logger = logging.getLogger(__name__)


def find_available_port() -> str:
    """Find an available port on localhost"""
    # TODO: replace find_available_port in CSharpExecutorProxy with this one
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        _, port = s.getsockname()
        return str(port)


def _resolve_python_flow_additional_includes(source) -> Path:
    # Resolve flow additional includes
    from promptflow.client import load_flow

    flow = load_flow(source)
    from promptflow._sdk.operations import FlowOperations

    with FlowOperations._resolve_additional_includes(flow.path) as resolved_flow_path:
        if resolved_flow_path == flow.path:
            return source
        # Copy resolved flow to temp folder if additional includes exists
        # Note: DO NOT use resolved flow path directly, as when inner logic raise exception,
        # temp dir will fail due to file occupied by other process.
        temp_flow_path = Path(tempfile.TemporaryDirectory().name)
        shutil.copytree(src=resolved_flow_path.parent, dst=temp_flow_path, dirs_exist_ok=True)

    return temp_flow_path


def start_flow_service(
    *,
    source: Path,
    static_folder: str = None,
    host: str = "localhost",
    port: int = 8080,
    config: dict = None,
    environment_variables: Dict[str, str] = None,
    init: Dict[str, Any] = None,
    skip_open_browser: bool = True,
):
    logger.info(
        "Start promptflow server with port %s",
        port,
    )
    language = resolve_flow_language(flow_path=source)

    flow_dir, flow_file_name = resolve_flow_path(source)

    os.environ["PROMPTFLOW_PROJECT_PATH"] = flow_dir.absolute().as_posix()
    if language == FlowLanguage.Python:
        helper = PythonFlowServiceHelper(
            flow_file_name=flow_file_name,
            flow_dir=flow_dir,
            init=init or {},
            port=port,
            static_folder=static_folder,
            host=host,
            config=config or {},
            environment_variables=environment_variables or {},
            skip_open_browser=skip_open_browser,
        )
    else:
        helper = CSharpFlowServiceHelper(
            flow_file_name=flow_file_name,
            flow_dir=flow_dir,
            init=init or {},
            port=port,
        )
    helper.run()


class BaseFlowServiceHelper:
    def __init__(self):
        pass

    @abc.abstractmethod
    def run(self):
        pass


class PythonFlowServiceHelper(BaseFlowServiceHelper):
    def __init__(
        self,
        *,
        flow_file_name,
        flow_dir,
        port,
        host,
        static_folder,
        config,
        environment_variables,
        init,
        skip_open_browser: bool,
    ):
        self._static_folder = static_folder
        self.flow_file_name = flow_file_name
        self.flow_dir = flow_dir
        self.host = host
        self.port = port
        self.config = config
        self.environment_variables = environment_variables
        self.init = init
        self.skip_open_browser = skip_open_browser
        super().__init__()

    @property
    def static_folder(self):
        if self._static_folder is None:
            return None
        return Path(self._static_folder).absolute().as_posix()

    def run(self):
        from promptflow._sdk._configuration import Configuration
        from promptflow.core._serving.app import create_app

        flow_dir = _resolve_python_flow_additional_includes(self.flow_dir / self.flow_file_name)

        pf_config = Configuration(overrides=self.config)
        logger.info(f"Promptflow config: {pf_config}")
        connection_provider = pf_config.get_connection_provider()
        os.environ["PROMPTFLOW_PROJECT_PATH"] = flow_dir.absolute().as_posix()
        logger.info(f"Change working directory to model dir {flow_dir}")
        os.chdir(flow_dir)
        app = create_app(
            static_folder=self.static_folder,
            environment_variables=self.environment_variables,
            connection_provider=connection_provider,
            init=self.init,
        )
        if not self.skip_open_browser:
            target = f"http://{self.host}:{self.port}"
            logger.info(f"Opening browser {target}...")
            webbrowser.open(target)
        # Debug is not supported for now as debug will rerun command, and we changed working directory.
        app.run(port=self.port, host=self.host)


class CSharpFlowServiceHelper(BaseFlowServiceHelper):
    def __init__(self, *, flow_file_name, flow_dir, init, port):
        self.port = port
        self._init = init
        self.flow_dir, self.flow_file_name = flow_dir, flow_file_name
        super().__init__()

    def _construct_command(self):
        return [
            "dotnet",
            EXECUTOR_SERVICE_DLL,
            "--port",
            str(self.port),
            "--yaml_path",
            self.flow_file_name,
            "--assembly_folder",
            ".",
            "--connection_provider_url",
            "",
            "--log_path",
            "",
            "--serving",
        ]

    def run(self):
        try:
            command = self._construct_command()
            subprocess.run(command, cwd=self.flow_dir, stdout=sys.stdout, stderr=sys.stderr)
        except KeyboardInterrupt:
            pass
