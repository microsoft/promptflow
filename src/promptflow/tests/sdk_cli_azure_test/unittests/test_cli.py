import os
import sys
from pathlib import Path
from typing import List
from unittest.mock import MagicMock

import pandas as pd
import pytest
from azure.ai.ml.constants._common import AZUREML_RESOURCE_PROVIDER, RESOURCE_ID_FORMAT
from pytest_mock import MockFixture

from promptflow._cli._pf_azure.entry import main
from promptflow._sdk._configuration import ConfigFileNotFound, Configuration
from promptflow._sdk._constants import VIS_PORTAL_URL_TMPL
from promptflow._utils.context_utils import _change_working_dir
from promptflow.azure.operations._run_operations import RunOperations

CONFIG_DATA_ROOT = Path(__file__).parent.parent.parent / "test_configs" / "configs"


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

    def test_get_workspace_from_config(self):
        # New instance instead of get_instance() to avoid side effect
        conf = Configuration(overrides={"connection.provider": "azureml"})
        # Test config within flow folder
        target_folder = CONFIG_DATA_ROOT / "mock_flow1"
        with _change_working_dir(target_folder):
            config1 = conf.get_connection_provider()
        assert config1 == "azureml:" + RESOURCE_ID_FORMAT.format("sub1", "rg1", AZUREML_RESOURCE_PROVIDER, "ws1")
        # Test config using flow parent folder
        target_folder = CONFIG_DATA_ROOT / "mock_flow2"
        with _change_working_dir(target_folder):
            config2 = conf.get_connection_provider()
        assert config2 == "azureml:" + RESOURCE_ID_FORMAT.format(
            "sub_default", "rg_default", AZUREML_RESOURCE_PROVIDER, "ws_default"
        )
        # Test config not found
        with pytest.raises(ConfigFileNotFound):
            Configuration._get_workspace_from_config(path=CONFIG_DATA_ROOT.parent)

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
            "--all-results",
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

    def test_run_visualize(
        self,
        default_subscription_id: str,
        default_resource_group: str,
        default_workspace: str,
        operation_scope_args: List[str],
        capfd: pytest.CaptureFixture,
    ) -> None:
        # cloud version visualize is actually a string concatenation
        names = "name1,name2,name3"
        run_pf_command(
            "run",
            "visualize",
            "--names",
            names,
            *operation_scope_args,
        )
        captured = capfd.readouterr()
        expected_portal_url = VIS_PORTAL_URL_TMPL.format(
            subscription_id=default_subscription_id,
            resource_group_name=default_resource_group,
            workspace_name=default_workspace,
            names=names,
        )
        assert expected_portal_url in captured.out

    def test_run_archive(
        self,
        mocker: MockFixture,
        operation_scope_args,
    ):
        mocked = mocker.patch.object(RunOperations, "archive")
        mocked.return_value._to_dict.return_value = {"name": "test_run"}
        run_pf_command(
            "run",
            "archive",
            "--name",
            "test_run",
            *operation_scope_args,
        )
        mocked.assert_called_once()

    def test_run_restore(
        self,
        mocker: MockFixture,
        operation_scope_args,
    ):
        mocked = mocker.patch.object(RunOperations, "restore")
        mocked.return_value._to_dict.return_value = {"name": "test_run"}
        run_pf_command(
            "run",
            "restore",
            "--name",
            "test_run",
            *operation_scope_args,
        )
        mocked.assert_called_once()

    def test_run_update(
        self,
        mocker: MockFixture,
        operation_scope_args,
    ):
        mocked = mocker.patch.object(RunOperations, "update")
        mocked.return_value._to_dict.return_value = {"name": "test_run"}
        run_pf_command(
            "run",
            "update",
            "--name",
            "test_run",
            "--set",
            "display_name=test_run",
            "description='test_description'",
            "tags.key1=value1",
            *operation_scope_args,
        )
        mocked.assert_called_once()
