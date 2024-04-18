import dataclasses
import json
import os
import os.path
import sys
from pathlib import Path

import pytest

from promptflow._cli._pf.entry import main


@dataclasses.dataclass
class FlowPaths:
    flow_dir: str
    data: str
    init: str

    def __init__(self, root_of_test_cases: Path, flow_name: str):
        self.flow_dir = (root_of_test_cases / flow_name / "bin" / "Debug" / "net6.0").as_posix()
        self.data = (root_of_test_cases / flow_name / "data.jsonl").as_posix()
        self.init = (root_of_test_cases / flow_name / "init.json").as_posix()

        if not os.path.exists(self.flow_dir):
            raise FileNotFoundError(f"Flow directory not found: {self.flow_dir}\n{os.listdir(root_of_test_cases)}")


@dataclasses.dataclass
class TestCases:
    basic: FlowPaths
    function_mode_basic: FlowPaths
    basic_with_builtin_llm: FlowPaths
    class_init_flex_flow: FlowPaths
    basic_chat: FlowPaths

    def __init__(self, root_of_test_cases: Path):
        self.basic = FlowPaths(root_of_test_cases, "Basic")
        self.function_mode_basic = FlowPaths(root_of_test_cases, "FunctionModeBasic")
        self.class_init_flex_flow = FlowPaths(root_of_test_cases, "ClassInitFlexFlow")
        self.basic_chat = FlowPaths(root_of_test_cases, "BasicChat")


@pytest.fixture(scope="session")
def root_test_cases() -> TestCases:
    target_path = os.getenv("CSHARP_TEST_CASES_ROOT", None)
    if target_path is None:
        pytest.skip("CSHARP_TEST_CASES_ROOT is not set.")
    target_path = Path(target_path)

    package_root = Path(__file__).parent.parent.parent.parent.parent / "promptflow"
    dev_connections_path = package_root / "connections.json"
    if not dev_connections_path.exists():
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


@pytest.mark.usefixtures(
    "use_secrets_config_file", "recording_injection", "setup_local_connection", "install_custom_tool_pkg"
)
@pytest.mark.cli_test
@pytest.mark.e2etest
class TestCSharpCli:
    def test_pf_flow_test_basic(self, root_test_cases: TestCases):
        run_pf_command(
            "flow",
            "test",
            "--flow",
            root_test_cases.basic.flow_dir,
            "--inputs",
            "question=what is promptflow?",
        )

    def test_flex_flow_test(self, root_test_cases: TestCases):
        run_pf_command(
            "flow",
            "test",
            "--flow",
            root_test_cases.function_mode_basic.flow_dir,
            "--inputs",
            "topic=promptflow",
        )

    @pytest.mark.skip(reason="need to update the test case")
    def test_pf_run_create_with_connection_override(self, root_test_cases: TestCases):
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

    def test_flow_chat(self, root_test_cases: TestCases, monkeypatch, capsys):
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
    def test_flow_chat_ui_streaming(self, root_test_cases: TestCases):
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
    def test_flow_chat_interactive_streaming(self, root_test_cases: TestCases, monkeypatch, capsys):
        flow_dir = f"{root_test_cases}\\examples\\BasicChatFlowWithBuiltinLLM\\bin\\Debug\\net6.0"
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

    @pytest.mark.skip(reason="need to update the test case")
    def test_flow_run_from_resume(self, root_test_cases: TestCases):
        run_pf_command("run", "create", "--resume-from", "net6_0_variant_0_20240326_163600_356909")

    @pytest.mark.skip(reason="need to avoid csharp calling local pfs to fetch connection")
    def test_flow_test_class_init(self, root_test_cases: TestCases):
        """Note that this test won't pass. Instead, it will hang and pop up a web page for user input.
        Leave it here for debugging purpose.
        """
        run_pf_command(
            "flow",
            "test",
            "--flow",
            root_test_cases.class_init_flex_flow.flow_dir,
            "--inputs",
            "question=aklhdfqwejk",
            "--init",
            "name=world",
            "connection=azure_open_ai_connection",
        )

    def test_pf_run_create_basic(self, root_test_cases: TestCases):
        run_pf_command(
            "run",
            "create",
            "--flow",
            root_test_cases.basic.flow_dir,
            "--data",
            root_test_cases.class_init_flex_flow.data,
            "--init",
            root_test_cases.class_init_flex_flow.init,
        )
