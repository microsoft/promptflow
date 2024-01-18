import tempfile
from pathlib import Path
import mock
import pytest
import sys
import os
import ast
import importlib

from .test_cli import run_pf_command

FLOWS_DIR = "./tests/test_configs/flows"
RUNS_DIR = "./tests/test_configs/runs"
CONNECTIONS_DIR = "./tests/test_configs/connections"
DATAS_DIR = "./tests/test_configs/datas"


@pytest.mark.usefixtures("use_secrets_config_file", "setup_local_connection", "install_custom_tool_pkg")
@pytest.mark.cli_test
@pytest.mark.e2etest
class TestExecutable:
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
                sys.path.append(temp_dir)
                for filename in os.listdir(temp_dir):
                    file_path = Path(temp_dir, filename)
                    if os.path.isfile(file_path) and filename.endswith('.py'):
                        with open(file_path, 'r') as file:
                            try:
                                tree = ast.parse(file.read())
                            except SyntaxError as e:
                                raise SyntaxError(f"Syntax error in file {file_path}: {e}")

                            for node in ast.walk(tree):
                                if isinstance(node, (ast.Import, ast.ImportFrom)):
                                    for alias in node.names:
                                        module_name = alias.name
                                        if isinstance(node, ast.ImportFrom):
                                            module_name = node.module
                                        try:
                                            module = importlib.import_module(module_name)
                                            if isinstance(node, ast.ImportFrom):
                                                getattr(module, alias.name)
                                        except ImportError:
                                            raise ImportError(f"Module {module_name} in file {file_path} "
                                                              f"does not exist")
                                        except AttributeError:
                                            module_name = f"{node.module}.{alias.name}"
                                            try:
                                                importlib.import_module(module_name)
                                            except ImportError:
                                                raise ImportError(
                                                    f"Cannot import {alias.name} from module {node.module} in "
                                                    f"file {file_path}")
