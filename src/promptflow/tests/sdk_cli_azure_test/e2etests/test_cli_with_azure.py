# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import contextlib
import os
import sys
import uuid
from typing import Callable

import pytest
from mock.mock import patch

from promptflow._constants import PF_USER_AGENT
from promptflow._sdk.entities import Run
from promptflow._utils.user_agent_utils import ClientUserAgentUtil
from promptflow._utils.utils import environment_variable_overwrite, parse_ua_to_dict
from promptflow.azure import PFClient
from promptflow.tracing._operation_context import OperationContext

from .._azure_utils import DEFAULT_TEST_TIMEOUT, PYTEST_TIMEOUT_METHOD
from ..recording_utilities import is_live

FLOWS_DIR = "./tests/test_configs/flows"
DATAS_DIR = "./tests/test_configs/datas"
RUNS_DIR = "./tests/test_configs/runs"


# TODO: move this to a shared utility module
def run_pf_command(*args, pf, runtime=None, cwd=None):
    from promptflow._cli._pf_azure.entry import main

    origin_argv, origin_cwd = sys.argv, os.path.abspath(os.curdir)
    try:
        sys.argv = (
            ["pfazure"]
            + list(args)
            + [
                "--subscription",
                pf._ml_client.subscription_id,
                "--resource-group",
                pf._ml_client.resource_group_name,
                "--workspace-name",
                pf._ml_client.workspace_name,
            ]
        )
        if runtime:
            sys.argv += ["--runtime", runtime]
        if cwd:
            os.chdir(cwd)
        main()
    finally:
        sys.argv = origin_argv
        os.chdir(origin_cwd)


@pytest.mark.timeout(timeout=DEFAULT_TEST_TIMEOUT, method=PYTEST_TIMEOUT_METHOD)
@pytest.mark.e2etest
@pytest.mark.usefixtures(
    "mock_get_azure_pf_client",
    "mock_set_headers_with_user_aml_token",
    "single_worker_thread_pool",
    "vcr_recording",
)
class TestCliWithAzure:
    def test_basic_flow_run_bulk_without_env(self, pf, runtime: str, randstr: Callable[[str], str]) -> None:
        name = randstr("name")
        run_pf_command(
            "run",
            "create",
            "--flow",
            f"{FLOWS_DIR}/web_classification",
            "--data",
            f"{DATAS_DIR}/webClassification3.jsonl",
            "--name",
            name,
            pf=pf,
            runtime=runtime,
        )
        run = pf.runs.get(run=name)
        assert isinstance(run, Run)

    @pytest.mark.skip("Custom tool pkg and promptprompt pkg with CustomStrongTypeConnection not installed on runtime.")
    def test_basic_flow_with_package_tool_with_custom_strong_type_connection(self, pf, runtime) -> None:
        name = str(uuid.uuid4())
        run_pf_command(
            "run",
            "create",
            "--flow",
            f"{FLOWS_DIR}/flow_with_package_tool_with_custom_strong_type_connection",
            "--data",
            f"{FLOWS_DIR}/flow_with_package_tool_with_custom_strong_type_connection/data.jsonl",
            "--name",
            name,
            pf=pf,
            runtime=runtime,
        )
        run = pf.runs.get(run=name)
        assert isinstance(run, Run)

    def test_run_with_remote_data(
        self, pf, runtime: str, remote_web_classification_data, randstr: Callable[[str], str]
    ) -> None:
        # run with arm id
        name = randstr("name1")
        run_pf_command(
            "run",
            "create",
            "--flow",
            "web_classification",
            "--data",
            f"azureml:{remote_web_classification_data.id}",
            "--name",
            name,
            pf=pf,
            runtime=runtime,
            cwd=f"{FLOWS_DIR}",
        )
        run = pf.runs.get(run=name)
        assert isinstance(run, Run)

        # run with name version
        name = randstr("name2")
        run_pf_command(
            "run",
            "create",
            "--flow",
            "web_classification",
            "--data",
            f"azureml:{remote_web_classification_data.name}:{remote_web_classification_data.version}",
            "--name",
            name,
            pf=pf,
            runtime=runtime,
            cwd=f"{FLOWS_DIR}",
        )
        run = pf.runs.get(run=name)
        assert isinstance(run, Run)

    def test_run_file_with_set(self, pf, runtime: str, randstr: Callable[[str], str]) -> None:
        name = randstr("name")
        run_pf_command(
            "run",
            "create",
            "--file",
            f"{RUNS_DIR}/run_with_env.yaml",
            "--set",
            f"runtime={runtime}",
            "--name",
            name,
            pf=pf,
        )
        run = pf.runs.get(run=name)
        assert isinstance(run, Run)
        assert run.properties["azureml.promptflow.runtime_name"] == runtime

    @pytest.mark.skipif(condition=not is_live(), reason="This test requires an actual PFClient")
    def test_azure_cli_ua(self, pf: PFClient):
        # clear user agent before test
        context = OperationContext().get_instance()
        context.user_agent = ""
        with environment_variable_overwrite(PF_USER_AGENT, ""):
            with pytest.raises(SystemExit):
                run_pf_command(
                    "run",
                    "show",
                    "--name",
                    "not_exist",
                    pf=pf,
                )
            user_agent = ClientUserAgentUtil.get_user_agent()
            ua_dict = parse_ua_to_dict(user_agent)
            assert ua_dict.keys() == {"promptflow-sdk", "promptflow-cli"}

    def test_cli_telemetry(self, pf, runtime: str, randstr: Callable[[str], str]) -> None:
        name = randstr("name")

        @contextlib.contextmanager
        def check_workspace_info(*args, **kwargs):
            if "custom_dimensions" in kwargs:
                assert kwargs["custom_dimensions"]["workspace_name"] == pf._ml_client.workspace_name
                assert kwargs["custom_dimensions"]["resource_group_name"] == pf._ml_client.resource_group_name
                assert kwargs["custom_dimensions"]["subscription_id"] == pf._ml_client.subscription_id
            yield None

        with patch("promptflow._sdk._telemetry.activity.log_activity") as mock_log_activity:
            mock_log_activity.side_effect = check_workspace_info
            run_pf_command(
                "run",
                "create",
                "--file",
                f"{RUNS_DIR}/run_with_env.yaml",
                "--set",
                f"runtime={runtime}",
                "--name",
                name,
                pf=pf,
            )
