import os
import sys
from unittest import mock
import pytest
from promptflow._cli._pf_azure.entry import main
from promptflow._core.operation_context import OperationContext
from promptflow._sdk._constants import USER_AGENT
from promptflow.azure.operations._run_operations import RunOperations

FLOWS_DIR = "./tests/test_configs/flows"
DATAS_DIR = "./tests/test_configs/datas"


def run_cli_command(cmd):
    with mock.patch.object(RunOperations, "create_or_update") as create_or_update_fun, \
            mock.patch.object(RunOperations, "update") as update_fun, \
            mock.patch.object(RunOperations, "get") as get_fun, \
            mock.patch.object(RunOperations, "restore") as restore_fun:
        create_or_update_fun.return_value._to_dict.return_value = {"name": "test_run"}
        update_fun.return_value._to_dict.return_value = {"name": "test_run"}
        get_fun.return_value._to_dict.return_value = {"name": "test_run"}
        restore_fun.return_value._to_dict.return_value = {"name": "test_run"}

        sys.argv = list(cmd)
        os.environ[USER_AGENT] = "perf_monitor/1.0"
        main()
        context = OperationContext.get_instance()
        assert "perf_monitor/1.0" in context.get_user_agent()


@pytest.fixture
def operation_scope_args(subscription_id: str, resource_group_name: str, workspace_name: str):
    return [
        "--subscription",
        subscription_id,
        "--resource-group",
        resource_group_name,
        "--workspace-name",
        workspace_name,
    ]


@pytest.mark.usefixtures("mock_get_azure_pf_client")
@pytest.mark.unittest
class TestAzureCliTimeConsume:
    def test_pfazure_run_create(self, operation_scope_args):
        run_cli_command(cmd=(
            "pfazure",
            "run",
            "create",
            "--flow",
            f"{FLOWS_DIR}/print_input_flow",
            "--data",
            f"{DATAS_DIR}/print_input_flow.jsonl",
            *operation_scope_args,
        ))


    def test_run_restore(self, operation_scope_args):
        run_cli_command(cmd=(
            "pfazure",
            "run",
            "restore",
            "--name",
            "test_run",
            *operation_scope_args,
        ))
