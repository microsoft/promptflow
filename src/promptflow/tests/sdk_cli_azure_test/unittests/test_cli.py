import os
import sys
from unittest.mock import MagicMock

import pandas as pd
import pytest
from pytest_mock import MockFixture

from promptflow._cli._pf_azure.entry import main
from promptflow.azure.operations._run_operations import RunOperations


def run_pf_command(*args, cwd=None):
    origin_argv, origin_cwd = sys.argv, os.path.abspath(os.curdir)
    try:
        sys.argv = ["pfazure"] + list(args)
        if cwd:
            os.chdir(cwd)
        main()
    finally:
        sys.argv = origin_argv
        os.chdir(origin_cwd)


@pytest.fixture
def operation_scope_args(default_subscription_id, default_resource_group, default_workspace):
    return [
        "--subscription",
        default_subscription_id,
        "--resource-group",
        default_resource_group,
        "--workspace-name",
        default_workspace,
    ]


@pytest.mark.unittest
class TestAzureCli:
    def test_pf_azure_version(self, capfd):
        run_pf_command("--version")
        out, err = capfd.readouterr()
        assert out == "0.0.1\n"

    def test_run_show(self, mocker: MockFixture, operation_scope_args):
        mocked = mocker.patch.object(RunOperations, "get")
        # show_run will print the run object, so we need to mock the return value
        mocked.return_value._to_dict.return_value = {"name": "test_run"}
        run_pf_command(
            "run",
            "show",
            "--name",
            "test_run",
            *operation_scope_args,
        )
        mocked.assert_called_once()

    def test_run_show_details(self, mocker: MockFixture, operation_scope_args):
        mocked = mocker.patch.object(RunOperations, "get_details")
        # show_run_details will print details, so we need to mock the return value
        mocked.return_value = pd.DataFrame([{"input": "input_value", "output": "output_value"}])
        run_pf_command(
            "run",
            "show-details",
            "--name",
            "test_run",
            "--max-results",
            "10",
            *operation_scope_args,
        )
        mocked.assert_called_once()

    def test_run_show_metrics(self, mocker: MockFixture, operation_scope_args):
        mocked = mocker.patch.object(RunOperations, "get_metrics")
        # show_metrics will print the metrics, so we need to mock the return value
        mocked.return_value = {"accuracy": 0.9}
        run_pf_command(
            "run",
            "show-metrics",
            "--name",
            "test_run",
            *operation_scope_args,
        )
        mocked.assert_called_once()

    def test_run_list_runs(
        self,
        mocker: MockFixture,
        operation_scope_args,
        default_subscription_id,
        default_resource_group,
        default_workspace,
    ):
        mocked_run = MagicMock()
        mocked_run._to_dict.return_value = {"name": "test_run"}
        mocked = mocker.patch.object(RunOperations, "list")
        # list_runs will print the run list, so we need to mock the return value
        mocked.return_value = [mocked_run]

        run_pf_command(
            "run",
            "list",
            "--max-results",
            "10",
            "--include-archived",
            *operation_scope_args,
        )
        run_pf_command(
            "run",
            "list",
            "--max-results",
            "10",
            "--include-archived",
            "--output",
            "table",
            *operation_scope_args,
        )

        mocker.patch.dict(
            os.environ,
            {
                "AZUREML_ARM_WORKSPACE_NAME": default_workspace,
                "AZUREML_ARM_SUBSCRIPTION": default_subscription_id,
                "AZUREML_ARM_RESOURCEGROUP": default_resource_group,
            },
        )
        run_pf_command(
            "run",
            "list",
            "--max-results",
            "10",
            "--include-archived",
        )
        assert mocked.call_count == 3
