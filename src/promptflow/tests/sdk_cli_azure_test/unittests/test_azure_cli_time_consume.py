import cProfile
import contextlib
import io
import multiprocessing
import pstats
import sys
import timeit
from unittest import mock
import pytest
from promptflow._cli._pf_azure.entry import main
from promptflow.azure.operations._run_operations import RunOperations

FLOWS_DIR = "./tests/test_configs/flows"
DATAS_DIR = "./tests/test_configs/datas"


def run_cli_command(cmd, time_limit=3600, result_queue=None):
    with mock.patch.object(RunOperations, "create_or_update") as create_or_update_fun, \
            mock.patch.object(RunOperations, "update") as update_fun, \
            mock.patch.object(RunOperations, "get") as get_fun, \
            mock.patch.object(RunOperations, "restore") as restore_fun:
        create_or_update_fun.return_value._to_dict.return_value = {"name": "test_run"}
        update_fun.return_value._to_dict.return_value = {"name": "test_run"}
        get_fun.return_value._to_dict.return_value = {"name": "test_run"}
        restore_fun.return_value._to_dict.return_value = {"name": "test_run"}

        sys.argv = list(cmd)
        output = io.StringIO()
        st = timeit.default_timer()
        with contextlib.redirect_stdout(output):
            main()
        ed = timeit.default_timer()
        print(f"Total time: {ed - st}s")
        assert ed - st < time_limit, f"The time limit is {time_limit}s, but it took {ed - st}s."
        res_value = output.getvalue()
        if result_queue:
            result_queue.put(res_value)
        return res_value


def subprocess_run_cli_command(cmd, time_limit=3600):
    result_queue = multiprocessing.Queue()
    process = multiprocessing.Process(target=run_cli_command, args=(cmd,), kwargs={"time_limit": time_limit,
                                                                                   "result_queue": result_queue})
    process.start()
    process.join()
    assert process.exitcode == 0
    return result_queue.get_nowait()


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


@pytest.mark.unittest
class TestAzureCliTimeConsume:
    def test_pfazure_run_create(self, operation_scope_args):
        subprocess_run_cli_command(cmd=(
            "pfazure",
            "run",
            "create",
            "--flow",
            f"{FLOWS_DIR}/print_input_flow",
            "--data",
            f"{DATAS_DIR}/print_input_flow.jsonl",
            *operation_scope_args,
        ), time_limit=8)

    def test_pfazure_run_update(self, operation_scope_args):
        subprocess_run_cli_command(cmd=(
            "pfazure",
            "run",
            "update",
            "--name",
            "test_run",
            "--set",
            "display_name=test_run",
            "description='test_description'",
            "tags.key1=value1",
            *operation_scope_args,
        ), time_limit=4)

    def test_run_restore(self, operation_scope_args,):
        subprocess_run_cli_command(cmd=(
            "pfazure",
            "run",
            "restore",
            "--name",
            "test_run",
            *operation_scope_args,
        ), time_limit=8)
