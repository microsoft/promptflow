import os
import os.path
import sys
from pathlib import Path

import pytest
from _constants import PROMPTFLOW_ROOT
from sdk_cli_azure_test.conftest import FLOWS_DIR

from promptflow._cli._pf.entry import main

RUNS_DIR = PROMPTFLOW_ROOT / "tests/test_configs/runs"
CONNECTIONS_DIR = PROMPTFLOW_ROOT / "tests/test_configs/connections"


# TODO: move this to a shared utility module
def run_pf_command(*args, cwd=None):
    """Run a pf command with the given arguments and working directory.

    There have been some unknown issues in using subprocess on CI, so we use this function instead, which will also
    provide better debugging experience.
    """
    origin_argv, origin_cwd = sys.argv, os.path.abspath(os.curdir)
    try:
        sys.argv = ["pf"] + list(args)
        if cwd:
            os.chdir(cwd)
        main()
    finally:
        sys.argv = origin_argv
        os.chdir(origin_cwd)


@pytest.mark.skipif(condition=not pytest.is_live, reason="CLI tests, only run in live mode.")
@pytest.mark.cli_test
@pytest.mark.e2etest
class TestCli:
    # PF cli test is here because when designate connection provider to remote, we need azure dependencies.
    def test_pf_flow_test(self, remote_workspace_resource_id):
        # Test with connection provider
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/web_classification",
            "--config",
            f"connection.provider={remote_workspace_resource_id}",
        )
        output_path = Path(FLOWS_DIR) / "web_classification" / ".promptflow" / "flow.output.json"
        assert output_path.exists()

    def test_flow_chat(self, monkeypatch, capsys, remote_workspace_resource_id):
        chat_list = ["hi", "what is chat gpt?"]

        def mock_input(*args, **kwargs):
            if chat_list:
                return chat_list.pop()
            else:
                raise KeyboardInterrupt()

        monkeypatch.setattr("builtins.input", mock_input)
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/chat_flow",
            "--interactive",
            "--verbose",
            "--config",
            f"connection.provider={remote_workspace_resource_id}",
        )
        output_path = Path(FLOWS_DIR) / "chat_flow" / ".promptflow" / "chat.output.json"
        assert output_path.exists()
        detail_path = Path(FLOWS_DIR) / "chat_flow" / ".promptflow" / "chat.detail.json"
        assert detail_path.exists()
        outerr = capsys.readouterr()
        # Check node output
        assert "chat_node:" in outerr.out
        assert "show_answer:" in outerr.out
        assert "[show_answer]: print:" in outerr.out
