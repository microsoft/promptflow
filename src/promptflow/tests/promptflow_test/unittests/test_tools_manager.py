import pytest

from promptflow.contracts.flow import ToolSource, ToolSourceType
from promptflow.contracts.tool import Tool
from promptflow.core.tools_manager import (
    CustomPythonToolLoadError,
    EmptyCodeInCustomTool,
    MissingTargetFunction,
    ToolsManager,
    collect_package_tools,
    gen_tool_by_source,
    reserved_keys,
)
from promptflow.exceptions import PackageToolNotFoundError


@pytest.mark.unittest
class TestToolsManager:
    def test_get_llm_reserved_keys(self) -> None:
        assert {
            "prompt",
            "connection",
            "model",
            "deployment_name",
            "suffix",
            "max_tokens",
            "temperature",
            "top_p",
            "n",
            "stream",
            "logprobs",
            "echo",
            "stop",
            "presence_penalty",
            "frequency_penalty",
            "best_of",
            "logit_bias",
            "user",
            "input",
            "functions",
            "function_call",
        } == reserved_keys

    @pytest.mark.parametrize(
        "code, error_code, message",
        [
            ("", EmptyCodeInCustomTool, "Missing code in node fake_name."),
            (
                "def fake_name()",
                CustomPythonToolLoadError,
                "Error when loading code of node fake_name: invalid syntax (<string>, line 1)",
            ),
            ("# Nothing", MissingTargetFunction, "Cannot find function tool_name in the code of node fake_name."),
        ],
    )
    def test_custom_python_meta(self, code, error_code, message) -> None:
        test_tool = Tool(name="tool_name", code=code, type="python", inputs=[])
        with pytest.raises(error_code) as ex:
            ToolsManager._load_custom_tool(test_tool, "fake_name")
        assert message == str(ex.value)

    def test_package_tool_not_found(self):
        tool_source = ToolSource(type=ToolSourceType.Package, tool="fake_name", path="fake_path")
        with pytest.raises(PackageToolNotFoundError) as ex:
            gen_tool_by_source("fake_name", tool_source, None, "fake_path"),
        error_message = (
            "Package tool 'fake_name' is not found in the current environment. "
            f"All available package tools are: {list(collect_package_tools())}."
        )
        assert str(ex.value) == error_message
