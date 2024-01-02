# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import importlib.util
from pathlib import Path

import pytest

TOOL_DIR = Path("./tests/test_configs/tools")


@pytest.mark.unittest
class TestTool:
    def get_tool_meta_by_path(self, client, tool_path, module_name):
        # Load the module from the file path
        spec = importlib.util.spec_from_file_location(module_name, tool_path)
        tool_module = importlib.util.module_from_spec(spec)

        # Load the module's code
        spec.loader.exec_module(tool_module)
        # List meta data of tools
        tool_meta = client.tools._generate_tool_meta(tool_module)
        return tool_meta

    def test_python_tool_meta(self, pf):
        tool_path = TOOL_DIR / "python_tool.py"
        tools_meta, _ = self.get_tool_meta_by_path(pf, tool_path, "python_tool")
        # Get python script tool meta
        expect_tools_meta = {
            "python_tool.my_python_tool": {
                "name": "python_tool",
                "type": "python",
                "inputs": {"input1": {"type": ["string"]}},
                "module": "python_tool",
                "function": "my_python_tool",
            },
            "python_tool.my_python_tool_without_name": {
                "name": "my_python_tool_without_name",
                "type": "python",
                "inputs": {"input1": {"type": ["string"]}},
                "module": "python_tool",
                "function": "my_python_tool_without_name",
            },
            "python_tool.PythonTool.python_tool": {
                "name": "PythonTool.python_tool",
                "type": "python",
                "inputs": {"connection": {"type": ["AzureOpenAIConnection"]}, "input1": {"type": ["string"]}},
                "module": "python_tool",
                "class_name": "PythonTool",
                "function": "python_tool",
            },
        }
        assert tools_meta == expect_tools_meta

    def test_custom_tool_meta(self, pf):
        tool_path = TOOL_DIR / "custom_llm_tool.py"
        tools_meta, _ = self.get_tool_meta_by_path(pf, tool_path, "custom_llm_tool")
        expect_meta = {
            "custom_llm_tool.TestCustomLLMTool.tool_func": {
                "class_name": "TestCustomLLMTool",
                "description": "This is a tool to demonstrate the custom_llm tool type",
                "enable_kwargs": True,
                "function": "tool_func",
                "inputs": {"api": {"type": ["string"]}, "connection": {"type": ["AzureOpenAIConnection"]}},
                "module": "custom_llm_tool",
                "name": "My Custom LLM Tool",
                "type": "custom_llm",
            },
            "custom_llm_tool.my_tool": {
                "description": "This is a tool to demonstrate the custom_llm tool type",
                "enable_kwargs": True,
                "function": "my_tool",
                "inputs": {"connection": {"type": ["CustomConnection"]}},
                "module": "custom_llm_tool",
                "name": "My Custom LLM Tool",
                "type": "custom_llm",
            },
        }
        assert tools_meta == expect_meta
