import json
import os
import os.path
import sys
from pathlib import Path
from typing import TypedDict

import pytest

from promptflow._cli._pf.entry import main
from promptflow._sdk._utilities.serve_utils import find_available_port


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


class CSharpProject(TypedDict):
    flow_dir: str
    data: str
    init: str


@pytest.mark.usefixtures(
    "use_secrets_config_file",
    "recording_injection",
    "setup_local_connection",
    "install_custom_tool_pkg",
)
@pytest.mark.cli_test
@pytest.mark.e2etest
@pytest.mark.csharp
class TestCSharpCli:
    @pytest.mark.parametrize(
        "target_fixture_name",
        [
            pytest.param("csharp_test_project_basic", id="basic"),
            pytest.param("csharp_test_project_basic_chat", id="basic_chat"),
            pytest.param("csharp_test_project_function_mode_basic", id="function_mode_basic"),
            pytest.param("csharp_test_project_class_init_flex_flow", id="class_init_flex_flow"),
        ],
    )
    def test_pf_run_create(self, request, target_fixture_name: str):
        test_case: CSharpProject = request.getfixturevalue(target_fixture_name)
        cmd = [
            "run",
            "create",
            "--flow",
            test_case["flow_dir"],
            "--data",
            test_case["data"],
        ]
        if os.path.exists(test_case["init"]):
            cmd.extend(["--init", test_case["init"]])
        run_pf_command(*cmd)

    @pytest.mark.parametrize(
        "target_fixture_name",
        [
            pytest.param("csharp_test_project_basic", id="basic"),
            pytest.param("csharp_test_project_basic_chat", id="basic_chat"),
            pytest.param("csharp_test_project_function_mode_basic", id="function_mode_basic"),
            pytest.param("csharp_test_project_class_init_flex_flow", id="class_init_flex_flow"),
        ],
    )
    def test_pf_flow_test(self, request, target_fixture_name: str):
        test_case: CSharpProject = request.getfixturevalue(target_fixture_name)
        with open(test_case["data"], "r") as f:
            lines = f.readlines()
        if len(lines) == 0:
            pytest.skip("No data provided for the test case.")
        inputs = json.loads(lines[0])
        if not isinstance(inputs, dict):
            pytest.skip("The first line of the data file should be a JSON object.")

        cmd = [
            "flow",
            "test",
            "--flow",
            test_case["flow_dir"],
            "--inputs",
        ]
        for key, value in inputs.items():
            if isinstance(value, (list, dict)):
                pytest.skip("TODO 3113715: ensure input type")
            if isinstance(value, str):
                value = f'"{value}"'
            cmd.extend([f"{key}={value}"])

        if os.path.exists(test_case["init"]):
            cmd.extend(["--init", test_case["init"]])
        run_pf_command(*cmd)

    @pytest.mark.skip(reason="need to figure out how to check serve status in subprocess")
    def test_flow_serve(self, csharp_test_project_class_init_flex_flow: CSharpProject):
        port = find_available_port()
        run_pf_command(
            "flow",
            "serve",
            "--source",
            csharp_test_project_class_init_flex_flow["flow_dir"],
            "--port",
            str(port),
            "--init",
            "connection=azure_open_ai_connection",
            "name=Promptflow",
        )

    @pytest.mark.skip(reason="need to figure out how to check serve status in subprocess")
    def test_flow_serve_init_json(self, csharp_test_project_class_init_flex_flow: CSharpProject):
        port = find_available_port()
        run_pf_command(
            "flow",
            "serve",
            "--source",
            csharp_test_project_class_init_flex_flow["flow_dir"],
            "--port",
            str(port),
            "--init",
            csharp_test_project_class_init_flex_flow["init"],
        )

    def test_flow_test_include_log(self, csharp_test_project_basic: CSharpProject, capfd):
        run_pf_command(
            "flow",
            "test",
            "--flow",
            csharp_test_project_basic["flow_dir"],
        )
        # use capfd to capture stdout and stderr redirected from subprocess
        captured = capfd.readouterr()
        assert "[TOOL.HelloWorld]" in captured.out

        run_pf_command(
            "run",
            "create",
            "--flow",
            csharp_test_project_basic["flow_dir"],
            "--data",
            csharp_test_project_basic["data"],
        )
        captured = capfd.readouterr()
        # info log shouldn't be printed
        assert "[TOOL.HelloWorld]" not in captured.out

    def test_flow_chat(self, monkeypatch, capsys, csharp_test_project_basic_chat: CSharpProject):
        flow_dir = csharp_test_project_basic_chat["flow_dir"]
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

        captured = capsys.readouterr()
        # Check node output
        assert "Hello world round 0: hi" in captured.out
        assert "Hello world round 1: what is chat gpt?" in captured.out

    @pytest.mark.skip(reason="need to update the test case")
    def test_pf_run_create_with_connection_override(self, csharp_test_project_basic):
        run_pf_command(
            "run",
            "create",
            "--flow",
            csharp_test_project_basic["flow_dir"],
            "--data",
            csharp_test_project_basic["data"],
            "--connections",
            "get_answer.connection=azure_open_ai_connection",
        )

    @pytest.mark.skip(reason="need to update the test case")
    def test_flow_chat_ui_streaming(self):
        pass

    @pytest.mark.skip(reason="need to update the test case")
    def test_flow_run_from_resume(self):
        run_pf_command("run", "create", "--resume-from", "net6_0_variant_0_20240326_163600_356909")
