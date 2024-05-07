import tempfile
from pathlib import Path

import pytest
from _constants import PROMPTFLOW_ROOT

from .test_cli import run_pf_command

FLOWS_DIR = PROMPTFLOW_ROOT / "tests/test_configs/flows"
RUNS_DIR = PROMPTFLOW_ROOT / "tests/test_configs/runs"
CONNECTIONS_DIR = PROMPTFLOW_ROOT / "tests/test_configs/connections"
DATAS_DIR = PROMPTFLOW_ROOT / "tests/test_configs/datas"


@pytest.mark.usefixtures("use_secrets_config_file", "setup_local_connection", "install_custom_tool_pkg")
@pytest.mark.cli_test
@pytest.mark.e2etest
class TestExecutable:
    def test_flow_build_executable(self):
        source = f"{FLOWS_DIR}/web_classification/flow.dag.yaml"
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
            check_path_list = [
                "flow/flow.dag.yaml",
                "connections/azure_open_ai_connection.yaml",
                "pf.bat",
                "pf",
                "start_pfs.vbs",
            ]
            output_path = Path(temp_dir).resolve()
            for check_path in check_path_list:
                check_path = output_path / check_path
                assert check_path.exists()
