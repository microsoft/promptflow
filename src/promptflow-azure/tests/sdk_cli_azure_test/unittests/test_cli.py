import contextlib
import os
import sys
from pathlib import Path
from typing import List
from unittest.mock import ANY, MagicMock, patch

import pandas as pd
import pytest
from pytest_mock import MockFixture
from sdk_cli_azure_test.conftest import FLOWS_DIR

from promptflow._sdk._constants import VIS_PORTAL_URL_TMPL


def run_pf_command(*args, cwd=None):
    from promptflow.azure._cli.entry import main

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
class TestAzureCli:
    def test_pf_azure_version(self, capfd):
        import re

        from pkg_resources import parse_version

        run_pf_command("--version")
        out, err = capfd.readouterr()

        pf_versions = re.findall(r'"\S+":\s+"(\S+)"', out)
        for pf_version in pf_versions:
            assert parse_version(pf_version)

    def test_run_show(self, mocker: MockFixture, operation_scope_args):
        from promptflow.azure.operations._run_operations import RunOperations

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
        from promptflow.azure.operations._run_operations import RunOperations

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
        from promptflow.azure.operations._run_operations import RunOperations

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
        subscription_id: str,
        resource_group_name: str,
        workspace_name: str,
    ):
        from promptflow.azure.operations._run_operations import RunOperations

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
                "AZUREML_ARM_WORKSPACE_NAME": workspace_name,
                "AZUREML_ARM_SUBSCRIPTION": subscription_id,
                "AZUREML_ARM_RESOURCEGROUP": resource_group_name,
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
        operation_scope_args: List[str],
        capfd: pytest.CaptureFixture,
        subscription_id: str,
        resource_group_name: str,
        workspace_name: str,
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
            subscription_id=subscription_id,
            resource_group_name=resource_group_name,
            workspace_name=workspace_name,
            names=names,
        )
        assert expected_portal_url in captured.out

    def test_run_archive(
        self,
        mocker: MockFixture,
        operation_scope_args,
    ):
        from promptflow.azure.operations._run_operations import RunOperations

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
        from promptflow.azure.operations._run_operations import RunOperations

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
        from promptflow.azure.operations._run_operations import RunOperations

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

    def test_flow_create(
        self,
        mocker: MockFixture,
        operation_scope_args,
    ):
        from promptflow.azure.operations._flow_operations import FlowOperations

        mocked = mocker.patch.object(FlowOperations, "create_or_update")
        mocked.return_value._to_dict.return_value = {"name": "test_run"}
        flow_dir = Path(FLOWS_DIR, "web_classification").resolve().as_posix()
        run_pf_command(
            "flow",
            "create",
            "--flow",
            flow_dir,
            "--set",
            "display_name=test_flow",
            "type=standard",
            "description='test_description'",
            "tags.key1=value1",
            *operation_scope_args,
        )
        mocked.assert_called_with(
            flow=flow_dir,
            display_name="test_flow",
            type="standard",
            description="test_description",
            tags={"key1": "value1"},
        )

    def test_flow_create_with_unknown_field(self, mocker: MockFixture, operation_scope_args):
        from promptflow.azure.operations._flow_operations import FlowOperations

        mocked = mocker.patch.object(FlowOperations, "create_or_update")
        mocked.return_value._to_dict.return_value = {"name": "test_run"}
        flow_dir = Path(FLOWS_DIR, "web_classification").resolve().as_posix()
        run_pf_command(
            "flow",
            "create",
            "--flow",
            flow_dir,
            "--set",
            "random_key=random_value",
            *operation_scope_args,
        )
        mocked.assert_called_with(flow=flow_dir, random_key="random_value")

    def test_flow_update(self, mocker: MockFixture, operation_scope_args):
        from promptflow.azure.operations._flow_operations import FlowOperations

        mocked = mocker.patch.object(FlowOperations, "_update_azure_flow")
        mocked.return_value._to_dict.return_value = {"name": "test_run"}
        run_pf_command(
            "flow",
            "update",
            "--flow",
            "test_flow",
            "--set",
            "display_name=test_flow_display_name",
            "description='test_description'",
            "tags.key1=value1",
            *operation_scope_args,
        )
        mocked.assert_called_with(
            flow=ANY,
            display_name="test_flow_display_name",
            description="test_description",
            tags={"key1": "value1"},
        )

    def test_flow_list(
        self,
        mocker: MockFixture,
        operation_scope_args,
    ):
        from promptflow.azure.operations._flow_operations import FlowOperations

        mocked_flow = MagicMock()
        mocked_flow._to_dict.return_value = {"name": "test_flow"}
        mocked = mocker.patch.object(FlowOperations, "list")
        mocked.return_value = [mocked_flow]
        run_pf_command(
            "flow",
            "list",
            "--max-results",
            "10",
            "--include-archived",
            "--type",
            "standard",
            "--include-others",
            "--output",
            "table",
            *operation_scope_args,
        )
        mocked.assert_called_once()

    def test_run_telemetry(
        self,
        mocker: MockFixture,
        operation_scope_args,
        subscription_id: str,
        resource_group_name: str,
        workspace_name: str,
    ):
        from promptflow.azure.operations._run_operations import RunOperations

        mocked_run = MagicMock()
        mocked_run._to_dict.return_value = {"name": "test_run"}
        mocked = mocker.patch.object(RunOperations, "list")
        # list_runs will print the run list, so we need to mock the return value
        mocked.return_value = [mocked_run]
        mocker.patch.dict(
            os.environ,
            {
                "AZUREML_ARM_WORKSPACE_NAME": workspace_name,
                "AZUREML_ARM_SUBSCRIPTION": subscription_id,
                "AZUREML_ARM_RESOURCEGROUP": resource_group_name,
            },
        )

        @contextlib.contextmanager
        def check_workspace_info(*args, **kwargs):
            if "custom_dimensions" in kwargs:
                assert kwargs["custom_dimensions"]["workspace_name"] == workspace_name
                assert kwargs["custom_dimensions"]["resource_group_name"] == resource_group_name
                assert kwargs["custom_dimensions"]["subscription_id"] == subscription_id
            yield None

        with patch("promptflow._sdk._telemetry.activity.log_activity") as mock_log_activity:
            mock_log_activity.side_effect = check_workspace_info
            run_pf_command(
                "run",
                "list",
                "--max-results",
                "10",
                "--include-archived",
                *operation_scope_args,
            )

    def test_run_download(self, mocker: MockFixture, operation_scope_args):
        from promptflow.azure.operations._run_operations import RunOperations

        mocked = mocker.patch.object(RunOperations, "download")
        mocked.return_value = "fake_output_run_dir"
        run_pf_command(
            "run",
            "download",
            "--name",
            "test_run",
            "--output",
            "fake_output_dir",
            "--overwrite",
            *operation_scope_args,
        )
        mocked.assert_called_once()

    def test_run_cancel(self, mocker: MockFixture, operation_scope_args):
        from promptflow.azure.operations._run_operations import RunOperations

        mocked = mocker.patch.object(RunOperations, "cancel")
        run_pf_command(
            "run",
            "cancel",
            "--name",
            "test_run",
            *operation_scope_args,
        )
        mocked.assert_called_once()
