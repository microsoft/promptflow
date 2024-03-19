import os
import sys
import timeit
from typing import Callable
from unittest import mock

import pytest
from sdk_cli_azure_test.recording_utilities import is_replay

from promptflow._cli._user_agent import USER_AGENT as CLI_USER_AGENT  # noqa: E402
from promptflow._sdk._telemetry import log_activity
from promptflow._utils.user_agent_utils import ClientUserAgentUtil

FLOWS_DIR = "./tests/test_configs/flows"
DATAS_DIR = "./tests/test_configs/datas"


def mock_log_activity(*args, **kwargs):
    custom_message = "github run: https://github.com/microsoft/promptflow/actions/runs/{0}".format(
        os.environ.get("GITHUB_RUN_ID")
    )
    if len(args) == 4:
        if args[3] is not None:
            args[3]["custom_message"] = custom_message
        else:
            args = list(args)
            args[3] = {"custom_message": custom_message}
    elif "custom_dimensions" in kwargs and kwargs["custom_dimensions"] is not None:
        kwargs["custom_dimensions"]["custom_message"] = custom_message
    else:
        kwargs["custom_dimensions"] = {"custom_message": custom_message}

    return log_activity(*args, **kwargs)


def run_cli_command(cmd, time_limit=3600):
    from promptflow._cli._pf_azure.entry import main

    sys.argv = list(cmd)
    st = timeit.default_timer()
    with mock.patch.object(ClientUserAgentUtil, "get_user_agent") as get_user_agent_fun, mock.patch(
        "promptflow._sdk._telemetry.activity.log_activity", side_effect=mock_log_activity
    ), mock.patch("promptflow._cli._utils.log_activity", side_effect=mock_log_activity):
        # Client side will modify user agent only through ClientUserAgentUtil to avoid impact executor/runtime.
        get_user_agent_fun.return_value = f"{CLI_USER_AGENT} perf_monitor/1.0"
        user_agent = ClientUserAgentUtil.get_user_agent()
        assert user_agent == f"{CLI_USER_AGENT} perf_monitor/1.0"
        main()
    ed = timeit.default_timer()

    print(f"{cmd}, \nTotal time: {ed - st}s")
    if is_replay():
        assert ed - st < time_limit, f"The time limit is {time_limit}s, but it took {ed - st}s."


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


@pytest.mark.perf_monitor_test
@pytest.mark.usefixtures(
    "mock_get_azure_pf_client",
    "mock_set_headers_with_user_aml_token",
    "single_worker_thread_pool",
    "vcr_recording",
)
class TestAzureCliPerf:
    def test_pfazure_run_create(self, operation_scope_args, randstr: Callable[[str], str], time_limit=15):
        name = randstr("name")
        run_cli_command(
            cmd=(
                "pfazure",
                "run",
                "create",
                "--flow",
                f"{FLOWS_DIR}/print_input_flow",
                "--data",
                f"{DATAS_DIR}/print_input_flow.jsonl",
                "--name",
                name,
                *operation_scope_args,
            ),
            time_limit=time_limit,
        )

    def test_pfazure_run_update(self, operation_scope_args, time_limit=15):
        run_cli_command(
            cmd=(
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
            ),
            time_limit=time_limit,
        )

    def test_run_restore(self, operation_scope_args, time_limit=15):
        run_cli_command(
            cmd=(
                "pfazure",
                "run",
                "restore",
                "--name",
                "test_run",
                *operation_scope_args,
            ),
            time_limit=time_limit,
        )
