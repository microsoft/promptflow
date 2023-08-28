import sys
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from promptflow._core._errors import PackageToolNotFoundError
from promptflow.contracts.run_info import Status
from promptflow.executor import FlowExecutor
from promptflow.executor._errors import NodeInputValidationError
from promptflow.executor.flow_executor import BulkResult, LineResult

from ..utils import WRONG_FLOW_ROOT, get_flow_package_tool_definition, get_flow_sample_inputs, get_yaml_file

PACKAGE_TOOL_BASE = Path(__file__).parent.parent / "package_tools"
sys.path.insert(0, str(PACKAGE_TOOL_BASE.resolve()))


@pytest.mark.e2etest
class TestPackageTool:
    def get_line_inputs(self, flow_folder=""):
        if flow_folder:
            inputs = self.get_bulk_inputs(flow_folder)
            return inputs[0]
        return {
            "url": "https://www.apple.com/shop/buy-iphone/iphone-14",
            "text": "some_text",
        }

    def get_bulk_inputs(self, nlinee=4, flow_folder=""):
        if flow_folder:
            inputs = get_flow_sample_inputs(flow_folder)
            if isinstance(inputs, list) and len(inputs) > 0:
                return inputs
            elif isinstance(inputs, dict):
                return [inputs]
            else:
                raise Exception(f"Invalid type of bulk input: {inputs}")
        return [self.get_line_inputs() for _ in range(nlinee)]

    def test_executor_package_tool_with_conn(self, mocker):
        flow_folder = PACKAGE_TOOL_BASE / "tool_with_connection"
        package_tool_definition = get_flow_package_tool_definition(flow_folder)
        mocker.patch("promptflow.tools.list.list_package_tools", return_value=package_tool_definition)
        name, secret = "dummy_name", "dummy_secret"
        connections = {"test_conn": {"type": "TestConnection", "value": {"name": name, "secret": secret}}}
        executor = FlowExecutor.create(get_yaml_file(flow_folder), connections, raise_ex=True)
        flow_result = executor.exec_line({})
        assert flow_result.run_info.status == Status.Completed
        assert len(flow_result.node_run_infos) == 1
        for _, v in flow_result.node_run_infos.items():
            assert v.status == Status.Completed
            assert v.output == name + secret

    def test_executor_package_with_prompt_tool(self, dev_connections, mocker):
        flow_folder = PACKAGE_TOOL_BASE / "custom_llm_tool"
        package_tool_definition = get_flow_package_tool_definition(flow_folder)
        mocker.patch("promptflow.executor._tool_resolver.collect_package_tools", return_value=package_tool_definition)
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections, raise_ex=True)
        run_id = str(uuid.uuid4())
        bulk_inputs = self.get_bulk_inputs(flow_folder=flow_folder)
        nlines = len(bulk_inputs)
        bulk_results = executor.exec_bulk(bulk_inputs, run_id)
        assert isinstance(bulk_results, BulkResult)
        for i in range(nlines):
            assert (
                bulk_results.outputs[i]["output"] == "Write a simple program that displays the greeting message: "
                f"\"{bulk_inputs[i]['text']}\" when executed.\n"
            )
        msg = f"Bulk result only has {len(bulk_results.line_results)}/{nlines} outputs"
        assert len(bulk_results.outputs) == nlines, msg
        for i, output in enumerate(bulk_results.outputs):
            assert isinstance(output, dict)
            assert "line_number" in output, f"line_number is not in {i}th output {output}"
            assert output["line_number"] == i, f"line_number is not correct in {i}th output {output}"
        msg = f"Bulk result only has {len(bulk_results.line_results)}/{nlines} line results"
        assert len(bulk_results.line_results) == nlines, msg
        for i, line_result in enumerate(bulk_results.line_results):
            assert isinstance(line_result, LineResult)
            assert line_result.run_info.status == Status.Completed, f"{i}th line got {line_result.run_info.status}"

    def test_custom_llm_tool_with_duplicated_inputs(self, dev_connections, mocker):
        flow_folder = PACKAGE_TOOL_BASE / "custom_llm_tool_with_duplicated_inputs"
        package_tool_definition = get_flow_package_tool_definition(flow_folder)
        mocker.patch("promptflow.executor._tool_resolver.collect_package_tools", return_value=package_tool_definition)
        msg = (
            "Invalid inputs {'api'} in prompt template of node custom_llm_tool_with_duplicated_inputs. "
            "These inputs are duplicated with the inputs of custom llm tool."
        )
        with pytest.raises(NodeInputValidationError, match=msg):
            FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)

    @pytest.mark.parametrize(
        "flow_folder, line_input, error_class, error_message",
        [
            (
                "wrong_tool_in_package_tools",
                {"text": "Best beijing hotel"},
                PackageToolNotFoundError,
                "Package tool 'promptflow.tools.serpapi.SerpAPI.search_11' is not found in the current environment. "
                "All available package tools are: "
                "['promptflow.tools.azure_content_safety.AzureContentSafety.analyze_text', "
                "'promptflow.tools.azure_detect.AzureDetect.get_language'].",
            ),
            (
                "wrong_package_in_package_tools",
                {"text": "Best beijing hotel"},
                PackageToolNotFoundError,
                "Package tool 'promptflow.tools.serpapi11.SerpAPI.search' is not found in the current environment. "
                "All available package tools are: "
                "['promptflow.tools.azure_content_safety.AzureContentSafety.analyze_text', "
                "'promptflow.tools.azure_detect.AzureDetect.get_language'].",
            ),
        ],
    )
    def test_package_tool_execution(self, flow_folder, line_input, error_class, error_message, dev_connections):
        def mock_collect_package_tools(keys=None):
            if keys is None:
                return {
                    "promptflow.tools.azure_content_safety.AzureContentSafety.analyze_text": None,
                    "promptflow.tools.azure_detect.AzureDetect.get_language": None,
                }  # Mock response for specific argument
            else:
                # Call the actual function with keys
                from promptflow._core.tools_manager import collect_package_tools

                return collect_package_tools(keys)

        with patch("promptflow.executor._tool_resolver.collect_package_tools", side_effect=mock_collect_package_tools):
            # ret = collect_package_tools()
            # print("hello" + json.dumps(ret))
            with pytest.raises(error_class) as exce_info:
                FlowExecutor.create(get_yaml_file(flow_folder, WRONG_FLOW_ROOT), dev_connections)
            assert error_message == exce_info.value.message
