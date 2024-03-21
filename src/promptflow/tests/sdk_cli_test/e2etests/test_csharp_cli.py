import os
import os.path
import sys
from pathlib import Path

import pytest

from promptflow._cli._pf.entry import main


def get_repo_base_path():
    return os.getenv("CSHARP_REPO_BASE_PATH", None)


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


@pytest.mark.usefixtures(
    "use_secrets_config_file", "recording_injection", "setup_local_connection", "install_custom_tool_pkg"
)
@pytest.mark.cli_test
@pytest.mark.e2etest
@pytest.mark.skipif(get_repo_base_path() is None, reason="available locally only before csharp support go public")
class TestCSharpCli:
    def test_pf_flow_test_basic(self):
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{get_repo_base_path()}\\src\\PromptflowCSharp\\Sample\\Basic\\bin\\Debug\\net6.0",
            "--inputs",
            "question=what is promptflow?",
        )

    def test_pf_flow_test_eager_mode(self):
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{get_repo_base_path()}\\src\\PromptflowCSharp\\TestCases\\FunctionModeBasic\\bin\\Debug\\net6.0",
            "--inputs",
            "topic=promptflow",
        )

    def test_pf_run_create_with_connection_override(self):
        run_pf_command(
            "run",
            "create",
            "--flow",
            f"{get_repo_base_path()}\\examples\\BasicWithBuiltinLLM\\bin\\Debug\\net6.0",
            "--data",
            f"{get_repo_base_path()}\\examples\\BasicWithBuiltinLLM\\batchRunData.jsonl",
            "--connections",
            "get_answer.connection=azure_open_ai_connection",
        )

    def test_flow_chat(self, monkeypatch, capsys):
        flow_dir = f"{get_repo_base_path()}\\src\\PromptflowCSharp\\Sample\\BasicChat\\bin\\Debug\\net6.0"
        # mock user input with pop so make chat list reversed
        chat_list = ["what is chat gpt?", "hi"]

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
            flow_dir,
            "--interactive",
            "--verbose",
        )
        output_path = Path(flow_dir) / ".promptflow" / "chat.output.json"
        assert output_path.exists()
        detail_path = Path(flow_dir) / ".promptflow" / "chat.detail.json"
        assert detail_path.exists()

        outerr = capsys.readouterr()
        # Check node output
        assert "Hello world round 0: hi" in outerr.out
        assert "Hello world round 1: what is chat gpt?" in outerr.out

    def test_flow_chat_ui_streaming(self):
        """Note that this test won't pass. Instead, it will hang and pop up a web page for user input.
        Leave it here for debugging purpose.
        """
        # The test need to interact with user input in ui
        flow_dir = f"{get_repo_base_path()}\\examples\\BasicChatFlowWithBuiltinLLM\\bin\\Debug\\net6.0"
        run_pf_command(
            "flow",
            "test",
            "--flow",
            flow_dir,
            "--ui",
        )

    def test_flow_chat_interactive_streaming(self, monkeypatch, capsys):
        flow_dir = f"{get_repo_base_path()}\\examples\\BasicChatFlowWithBuiltinLLM\\bin\\Debug\\net6.0"
        # mock user input with pop so make chat list reversed
        chat_list = ["what is chat gpt?", "hi"]

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
            flow_dir,
            "--interactive",
            "--verbose",
        )
        output_path = Path(flow_dir) / ".promptflow" / "chat.output.json"
        assert output_path.exists()
        detail_path = Path(flow_dir) / ".promptflow" / "chat.detail.json"
        assert detail_path.exists()

        outerr = capsys.readouterr()
        # Check node output
        assert "language model" in outerr.out
