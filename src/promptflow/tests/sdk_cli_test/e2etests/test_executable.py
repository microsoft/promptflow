import subprocess
import sys
import tempfile
from pathlib import Path

import mock
import pytest

from .test_cli import run_pf_command

FLOWS_DIR = "./tests/test_configs/flows"
RUNS_DIR = "./tests/test_configs/runs"
CONNECTIONS_DIR = "./tests/test_configs/connections"
DATAS_DIR = "./tests/test_configs/datas"


@pytest.mark.usefixtures("use_secrets_config_file", "setup_local_connection", "install_custom_tool_pkg")
@pytest.mark.cli_test
@pytest.mark.e2etest
class TestExecutable:
    @pytest.mark.skipif(
        sys.platform == "win32" or sys.platform == "darwin",
        reason="Raise Exception: Process terminated with exit code 4294967295",
    )
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
                process = subprocess.Popen(["python", app_file], stderr=subprocess.PIPE)
                try:
                    # Wait for a specified time (in seconds)
                    wait_time = 5
                    process.wait(timeout=wait_time)
                    if process.returncode == 0:
                        pass
                    else:
                        raise Exception(
                            f"Process terminated with exit code {process.returncode}, "
                            f"{process.stderr.read().decode('utf-8')}"
                        )
                except (subprocess.TimeoutExpired, KeyboardInterrupt):
                    pass
                finally:
                    # Kill the process
                    process.terminate()
                    process.wait()  # Ensure the process is fully terminated
