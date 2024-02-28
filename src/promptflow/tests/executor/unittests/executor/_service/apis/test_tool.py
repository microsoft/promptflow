from typing import List, Tuple

import pytest
from fastapi.testclient import TestClient

from .....utils import get_flow_folder


def construct_tool_meta_request_json(flow_folder: str, tools: List[Tuple[str, str]]):
    working_dir = get_flow_folder(flow_folder)
    tools = {source: {"tool_type": tool_type} for source, tool_type in tools}
    return {
        "working_dir": working_dir.as_posix(),
        "tools": tools,
    }


@pytest.mark.unittest
class TestToolApis:
    def test_list_package_tools(self, executor_client: TestClient):
        response = executor_client.get(url="/tool/package_tools")
        assert response.status_code == 200
        package_tools = response.json()
        assert len(package_tools) > 0
        assert isinstance(package_tools, dict)
        assert all(isinstance(tool, dict) for tool in package_tools.values())

    def test_gen_tool_meta_all_completed(self, executor_client: TestClient):
        flow_folder = "web_classification"
        tools = [
            ("fetch_text_content_from_url.py", "python"),
            ("prepare_examples.py", "python"),
            ("classify_with_llm.jinja2", "llm"),
            ("convert_to_dict.py", "python"),
        ]
        request = construct_tool_meta_request_json(flow_folder, tools)
        response = executor_client.post(url="/tool/meta", json=request)
        # assert response
        assert response.status_code == 200
        tool_meta = response.json()
        assert len(tool_meta["tools"]) == len(tools)
        assert len(tool_meta["errors"]) == 0

    def test_gen_tool_meta_partial_failed(self):
        pass
