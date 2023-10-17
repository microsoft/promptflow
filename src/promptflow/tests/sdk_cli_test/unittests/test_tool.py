# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path
import importlib.util
import pytest

from promptflow._sdk._pf_client import PFClient


TOOL_DIR = Path("./tests/test_configs/tools")


@pytest.mark.unittest
class TestTool:

    def __init__(self):
        self.pf_client = PFClient()

    def get_tool_meta_by_path(self, tool_path, module_name):
        # Load the module from the file path
        spec = importlib.util.spec_from_file_location(module_name, tool_path)
        tool_module = importlib.util.module_from_spec(spec)

        # Load the module's code
        spec.loader.exec_module(tool_module)
        # List meta data of tools
        tool_meta = self.client._tools.generate_tool_meta(tool_module)
        return tool_meta

    def test_python_tool_meta(self):
        tool_path = TOOL_DIR / "python_tool.py"
        tools_meta = self.get_tool_meta_by_path(tool_path, "python_tool")
        # Get python script tool meta
        expect_tools_meta = {
            'python_tool.my_python_tool':
                {
                    'name': 'python_tool',
                    'type': 'python',
                    'inputs': {'input1': {'type': ['string']}},
                    'module': 'python_tool',
                    'function': 'my_python_tool'
                },
            'python_tool.my_python_tool_without_name':
                {
                    'name': 'my_python_tool_without_name',
                    'type': 'python',
                    'inputs': {'input1': {'type': ['string']}},
                    'module': 'python_tool',
                    'function': 'my_python_tool_without_name'
                },
            'python_tool.PythonTool.python_tool':
                {
                    'name': 'PythonTool.python_tool',
                    'type': 'python',
                    'inputs': {
                        'connection': {'type': ['AzureOpenAIConnection']},
                        'input1': {'type': ['string']}
                    },
                    'module': 'python_tool',
                    'class_name': 'PythonTool',
                    'function': 'python_tool'
                }
        }
        assert tools_meta == expect_tools_meta

    def test_custom_tool_meta(self):
        tool_path = TOOL_DIR / "custom_llm_tool.py"
        tools_meta = self.get_tool_meta_by_path(tool_path, "custom_llm_tool")
        expect_meta = {
            'custom_llm_tool.TestCustomLLMTool.tool_func':
                {
                    'name': 'custom_llm_tool',
                    'type': 'custom_llm',
                    'inputs': {
                        'connection': {'type': ['AzureOpenAIConnection']},
                        'api': {'type': ['string']},
                        'template': {'type': ['prompt_template']}
                    },
                    'module': 'custom_llm_tool',
                    'class_name': 'TestCustomLLMTool',
                    'function': 'tool_func'}
        }
        assert tools_meta == expect_meta
