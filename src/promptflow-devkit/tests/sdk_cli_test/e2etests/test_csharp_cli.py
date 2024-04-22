import dataclasses
import json
import os
import os.path
import sys
from pathlib import Path
from typing import Optional

import pytest

from promptflow._cli._pf.entry import main


class TestCase:
    def __init__(self, root_of_test_cases: Path, flow_name: str, skip_reason: str = None):
        self._flow_dir = (root_of_test_cases / flow_name / "bin" / "Debug" / "net6.0").as_posix()
        self.data = (root_of_test_cases / flow_name / "data.jsonl").as_posix()
        self.init = (root_of_test_cases / flow_name / "init.json").as_posix()
        self._skip_reason = skip_reason

    @property
    def flow_dir(self):
        if self._skip_reason:
            pytest.skip(self._skip_reason)
        return self._flow_dir


@dataclasses.dataclass
class TestCases:
    basic: TestCase
    function_mode_basic: TestCase
    basic_with_builtin_llm: TestCase
    class_init_flex_flow: TestCase
    basic_chat: TestCase

    def __init__(self, root_of_test_cases: Path):
        is_in_ci_pipeline = os.getenv("IS_IN_CI_PIPELINE", "false").lower() == "true"
        self.basic = TestCase(root_of_test_cases, "Basic")
        self.function_mode_basic = TestCase(root_of_test_cases, "FunctionModeBasic")
        self.class_init_flex_flow = TestCase(
            root_of_test_cases,
            "ClassInitFlexFlow",
            "need to avoid fetching connection from local pfs to enable this in ci" if is_in_ci_pipeline else None,
        )
        self.basic_chat = TestCase(root_of_test_cases, "BasicChat")

        package_root = Path(__file__).parent.parent.parent.parent.parent / "promptflow"
        dev_connections_path = package_root / "connections.json"

        if is_in_ci_pipeline and not dev_connections_path.exists():
            dev_connections_path.write_text(
                json.dumps(
                    {
                        "azure_open_ai_connection": {
                            "type": "AzureOpenAIConnection",
                            "value": {
                                "api_key": os.getenv("AZURE_OPENAI_API_KEY", "00000000000000000000000000000000"),
                                "api_base": os.getenv("AZURE_OPENAI_ENDPOINT", "https://openai.azure.com/"),
                                "api_type": "azure",
                                "api_version": "2023-07-01-preview",
                            },
                            "module": "promptflow.connections",
                        }
                    }
                )
            )
            print(f"Using dev connections file: {dev_connections_path}")


def get_root_test_cases() -> Optional[TestCases]:
    target_path = os.getenv("CSHARP_TEST_CASES_ROOT", None)
    target_path = Path(target_path or Path(__file__).parent)
    return TestCases(target_path)


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


root_test_cases = get_root_test_cases()


@pytest.mark.usefixtures(
    "use_secrets_config_file", "recording_injection", "setup_local_connection", "install_custom_tool_pkg"
)
@pytest.mark.cli_test
@pytest.mark.e2etest
@pytest.mark.skipif(
    not os.getenv("CSHARP_TEST_CASES_ROOT", None), reason="No C# test cases found, please set CSHARP_TEST_CASES_ROOT."
)
class TestCSharpCli:
    @pytest.mark.parametrize(
        "test_case",
        [
            pytest.param(root_test_cases.basic, id="basic"),
            pytest.param(root_test_cases.basic_chat, id="basic_chat"),
            pytest.param(root_test_cases.function_mode_basic, id="function_mode_basic"),
            pytest.param(root_test_cases.class_init_flex_flow, id="class_init_flex_flow"),
        ],
    )
    def test_pf_run_create(self, test_case: TestCase):
        cmd = [
            "run",
            "create",
            "--flow",
            test_case.flow_dir,
            "--data",
            test_case.data,
        ]
        if os.path.exists(test_case.init):
            cmd.extend(["--init", test_case.init])
        run_pf_command(*cmd)

    @pytest.mark.parametrize(
        "test_case",
        [
            pytest.param(root_test_cases.basic, id="basic"),
            pytest.param(root_test_cases.basic_chat, id="basic_chat"),
            pytest.param(root_test_cases.function_mode_basic, id="function_mode_basic"),
            pytest.param(root_test_cases.class_init_flex_flow, id="class_init_flex_flow"),
        ],
    )
    def test_pf_flow_test(self, test_case: TestCase):
        with open(test_case.data, "r") as f:
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
            test_case.flow_dir,
            "--inputs",
        ]
        for key, value in inputs.items():
            if isinstance(value, (list, dict)):
                pytest.skip("TODO 3113715: ensure input type")
            if isinstance(value, str):
                value = f'"{value}"'
            cmd.extend([f"{key}={value}"])

        if os.path.exists(test_case.init):
            cmd.extend(["--init", test_case.init])
        run_pf_command(*cmd)

    def test_flow_chat(self, monkeypatch, capsys):
        flow_dir = root_test_cases.basic_chat.flow_dir
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

    @pytest.mark.skip(reason="need to update the test case")
    def test_pf_run_create_with_connection_override(self):
        run_pf_command(
            "run",
            "create",
            "--flow",
            root_test_cases.basic_with_builtin_llm.flow_dir,
            "--data",
            root_test_cases.basic_with_builtin_llm.data,
            "--connections",
            "get_answer.connection=azure_open_ai_connection",
        )

    @pytest.mark.skip(reason="need to update the test case")
    def test_flow_chat_ui_streaming(self):
        """Note that this test won't pass. Instead, it will hang and pop up a web page for user input.
        Leave it here for debugging purpose.
        """
        # The test need to interact with user input in ui
        flow_dir = f"{root_test_cases}\\examples\\BasicChatFlowWithBuiltinLLM\\bin\\Debug\\net6.0"
        run_pf_command(
            "flow",
            "test",
            "--flow",
            flow_dir,
            "--ui",
        )

    @pytest.mark.skip(reason="need to update the test case")
    def test_flow_run_from_resume(self):
        run_pf_command("run", "create", "--resume-from", "net6_0_variant_0_20240326_163600_356909")
