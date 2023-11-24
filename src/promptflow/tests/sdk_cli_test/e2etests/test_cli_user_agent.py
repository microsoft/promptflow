import os
import sys
import uuid

import pytest
from promptflow._cli._pf.entry import main
import multiprocessing
from promptflow._core.operation_context import OperationContext
from promptflow._sdk._constants import USER_AGENT

FLOWS_DIR = "./tests/test_configs/flows"
CONNECTIONS_DIR = "./tests/test_configs/connections"
DATAS_DIR = "./tests/test_configs/datas"


def run_cli_command(cmd):
    os.environ[USER_AGENT] = "perf_monitor/1.0"
    sys.argv = list(cmd)
    main()
    context = OperationContext.get_instance()
    assert "perf_monitor/1.0" in context.get_user_agent()


def subprocess_run_cli_command(cmd):
    process = multiprocessing.Process(target=run_cli_command, args=(cmd,))
    process.start()
    process.join()
    assert process.exitcode == 0


@pytest.mark.usefixtures("use_secrets_config_file", "setup_local_connection")
@pytest.mark.cli_test
@pytest.mark.e2etest
class TestCliTimeConsume:
    def test_pf_run_create(self) -> None:
        subprocess_run_cli_command(cmd=(
            "pf",
            "run",
            "create",
            "--flow",
            f"{FLOWS_DIR}/print_input_flow",
            "--data",
            f"{DATAS_DIR}/print_input_flow.jsonl",
        ))


    def test_pf_flow_test(self):
        subprocess_run_cli_command(cmd=(
            "pf",
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/print_input_flow",
            "--inputs",
            "text=https://www.youtube.com/watch?v=o5ZQyXaAv1g",
        ))


    def test_pf_connection_create(self):
        name = f"Connection_{str(uuid.uuid4())[:4]}"
        subprocess_run_cli_command(cmd=(
            "pf",
            "connection",
            "create",
            "--file",
            f"{CONNECTIONS_DIR}/azure_openai_connection.yaml",
            "--name",
            f"{name}",
        ))