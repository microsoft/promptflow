import subprocess
import tempfile
from pathlib import Path
import mock
import pytest
import time
import requests
import platform
import sys

from .test_cli import run_pf_command

FLOWS_DIR = "./tests/test_configs/flows"
RUNS_DIR = "./tests/test_configs/runs"
CONNECTIONS_DIR = "./tests/test_configs/connections"
DATAS_DIR = "./tests/test_configs/datas"


@pytest.mark.usefixtures("use_secrets_config_file", "setup_local_connection", "install_custom_tool_pkg")
@pytest.mark.cli_test
@pytest.mark.e2etest
class TestExecutable:
    # @pytest.mark.skipif(
    #     sys.platform == "win32" or sys.platform == "darwin",
    #     reason="Raise Exception: Process terminated with exit code 4294967295",
    # )
    def test_flow_build_executable(self):
        source = f"{FLOWS_DIR}/web_classification/flow.dag.yaml"
        target = "promptflow._sdk.operations._flow_operations.FlowOperations._run_pyinstaller"
        with mock.patch(target) as mocked:
            mocked.return_value = None

            with tempfile.TemporaryDirectory() as temp_dir:
                run_pf_command(
                    "flow",
                    "build",
                    "--source",
                    source,
                    "--output",
                    temp_dir,
                    "--format",
                    "executable",
                )
                # Start the Python script as a subprocess
                app_file = Path(temp_dir, "app.py").as_posix()
                if not Path(app_file).exists():
                    raise Exception(f"File {app_file} does not exist.")
                process = subprocess.Popen([sys.executable, app_file], stderr=subprocess.PIPE, shell=platform.system() == 'Windows')
                time.sleep(5)
                try:
                    error_message = process.stderr.read().decode("utf-8")
                    if process.poll() is not None:
                        print(f"Error output from child process: {error_message}")
                        raise Exception(f"Streamlit server did not start successfully. "
                                        f"error code: {process.returncode} message:{error_message}")
                    else:
                        try:
                            response = requests.get("http://localhost:8501")
                            if response.status_code == 200:
                                print("Streamlit server started successfully.")
                            else:
                                raise Exception(f"Streamlit server did not start successfully. "
                                                f"error code: {process.returncode} message:{error_message}")
                        except requests.exceptions.ConnectionError:
                            raise Exception(f"Could not connect to Streamlit server. error code: "
                                            f"{process.returncode} message:{error_message}")
                finally:
                    process.terminate()
                    process.wait()