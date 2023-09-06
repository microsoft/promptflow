import sys
from pathlib import Path

import pytest

from promptflow.connections import AzureOpenAIConnection
from promptflow.contracts.flow import InputAssignment, InputValueType, Node, ToolSourceType
from promptflow.contracts.tool import InputDefinition, Tool, ToolType, ValueType
from promptflow.exceptions import UserErrorException
from promptflow.executor._errors import (
    ConnectionNotFound,
    InvalidConnectionType,
    NodeInputValidationError,
    ValueTypeUnresolved,
)
from promptflow.executor._tool_resolver import ToolResolver

TEST_ROOT = Path(__file__).parent.parent.parent
REQUESTS_PATH = TEST_ROOT / "test_configs/executor_api_requests"
WRONG_REQUESTS_PATH = TEST_ROOT / "test_configs/executor_wrong_requests"


@pytest.mark.unittest
class TestToolResolver:
    @pytest.fixture
    def resolver(self):
        return ToolResolver(working_dir=None, connections={})

    def test_resolve_tool_by_node_with_diff_type(self, resolver, mocker):
        node = mocker.Mock(name="node", tool=None, inputs={})
        node.source = mocker.Mock(type=ToolSourceType.Package)

        mocker.patch.object(
            resolver,
            "_resolve_package_node",
            return_value=mocker.Mock(node=node, definition=None, callable=None, init_args=None),
        )
        mocker.patch.object(
            resolver,
            "_resolve_script_node",
            return_value=mocker.Mock(node=node, definition=None, callable=None, init_args=None),
        )
        mocker.patch.object(
            resolver,
            "_resolve_prompt_node",
            return_value=mocker.Mock(node=node, definition=None, callable=None, init_args=None),
        )
        mocker.patch.object(
            resolver,
            "_resolve_llm_node",
            return_value=mocker.Mock(node=node, definition=None, callable=None, init_args=None),
        )

        node.type = ToolType.PYTHON
        resolver.resolve_tool_by_node(node)
        resolver._resolve_package_node.assert_called_once()

        node.type = ToolType.PYTHON
        node.source = mocker.Mock(type=ToolSourceType.Code)
        resolver.resolve_tool_by_node(node)
        resolver._resolve_script_node.assert_called_once()

        node.type = ToolType.PROMPT
        resolver._resolve_prompt_node(node)
        resolver._resolve_prompt_node.assert_called_once()

        node.type = ToolType.LLM
        resolver._resolve_llm_node(node)
        resolver._resolve_llm_node.assert_called_once()

    def test_resolve_tool_by_node_with_invalid_type(self, resolver, mocker):
        node = mocker.Mock(name="node", tool=None, inputs={})
        node.source = mocker.Mock(type=None)

        with pytest.raises(NotImplementedError) as exec_info:
            resolver.resolve_tool_by_node(node)
        assert "Tool type" in exec_info.value.args[0]

    def test_resolve_tool_by_node_with_invalid_source_type(self, resolver, mocker):
        node = mocker.Mock(name="node", tool=None, inputs={})
        node.type = ToolType.PYTHON
        node.source = mocker.Mock(type=None)

        with pytest.raises(NotImplementedError) as exec_info:
            resolver.resolve_tool_by_node(node)
        assert "Tool source type" in exec_info.value.args[0]

    def test_resolve_tool_by_node_with_no_source(self, resolver, mocker):
        node = mocker.Mock(name="node", tool=None, inputs={})
        node.source = None

        with pytest.raises(UserErrorException):
            resolver.resolve_tool_by_node(node)

    def test_ensure_node_inputs_type(self):
        # Case 1: conn_name not in connections, should raise conn_name not found error
        tool = Tool(name="mock", type="python", inputs={"conn": InputDefinition(type=["CustomConnection"])})
        node = Node(
            name="mock",
            tool=tool,
            inputs={"conn": InputAssignment(value="conn_name", value_type=InputValueType.LITERAL)},
        )
        connections = {}
        with pytest.raises(ConnectionNotFound):
            tool_resolver = ToolResolver(working_dir=None, connections=connections)
            tool_resolver._convert_node_literal_input_types(node, tool)

        # Case 2: conn_name in connections, but type not matched
        connections = {"conn_name": {"type": "AzureOpenAIConnection", "value": {"api_key": "mock", "api_base": "mock"}}}
        with pytest.raises(NodeInputValidationError) as e:
            tool_resolver = ToolResolver(working_dir=None, connections=connections)
            tool_resolver._convert_node_literal_input_types(node, tool)
        message = "'AzureOpenAIConnection' is not supported, valid types ['CustomConnection']"
        assert message in str(e.value), "Expected: {}, Actual: {}".format(message, str(e.value))

        # Case 3: Literal value, type mismatch
        tool = Tool(name="mock", type="python", inputs={"int_input": InputDefinition(type=[ValueType.INT])})
        node = Node(
            name="mock",
            tool=tool,
            inputs={"int_input": InputAssignment(value="invalid", value_type=InputValueType.LITERAL)},
        )
        connections = {}
        with pytest.raises(NodeInputValidationError) as e:
            tool_resolver = ToolResolver(working_dir=None, connections=connections)
            tool_resolver._convert_node_literal_input_types(node, tool)
        if (sys.version_info.major == 3) and (sys.version_info.minor >= 11):
            # Python >= 3.11 has a different error message on linux and macos
            message = "value invalid is not type ValueType.INT"
        else:
            message = "value invalid is not type int"
        assert message in str(e.value), "Expected: {}, Actual: {}".format(message, str(e.value))

        # Case 4: Unresolved value, like newly added type not in old version ValueType enum
        tool = Tool(name="mock", type="python", inputs={"int_input": InputDefinition(type=["A_good_type"])})
        node = Node(
            name="mock",
            tool=tool,
            inputs={"int_input": InputAssignment(value="invalid", value_type=InputValueType.LITERAL)},
        )
        connections = {}
        with pytest.raises(ValueTypeUnresolved):
            tool_resolver = ToolResolver(working_dir=None, connections=connections)
            tool_resolver._convert_node_literal_input_types(node, tool)

    def test_resolve_llm_connection_to_inputs(self):
        # Case 1: node.connection is not specified
        tool = Tool(name="mock", type="python", inputs={"conn": InputDefinition(type=["CustomConnection"])})
        node = Node(
            name="mock",
            tool=tool,
            inputs={"conn": InputAssignment(value="conn_name", value_type=InputValueType.LITERAL)},
        )
        connections = {"conn_name": {"type": "AzureOpenAIConnection", "value": {"api_key": "mock", "api_base": "mock"}}}
        with pytest.raises(ConnectionNotFound):
            tool_resolver = ToolResolver(working_dir=None, connections=connections)
            tool_resolver._resolve_llm_connection_to_inputs(node, tool)

        # Case 2: node.connection is not found from connection manager
        tool = Tool(name="mock", type="python", inputs={"conn": InputDefinition(type=["CustomConnection"])})
        node = Node(
            name="mock",
            tool=tool,
            inputs={"conn": InputAssignment(value="conn_name", value_type=InputValueType.LITERAL)},
            connection="conn_name1",
        )
        connections = {}
        with pytest.raises(ConnectionNotFound):
            tool_resolver = ToolResolver(working_dir=None, connections=connections)
            tool_resolver._resolve_llm_connection_to_inputs(node, tool)

        # Case 3: Tool definition with bad input type list
        tool = Tool(name="mock", type="python", inputs={"conn": InputDefinition(type=["int"])})
        node = Node(
            name="mock",
            tool=tool,
            inputs={"conn": InputAssignment(value="conn_name", value_type=InputValueType.LITERAL)},
            connection="conn_name",
        )
        connections = {"conn_name": {"type": "AzureOpenAIConnection", "value": {"api_key": "mock", "api_base": "mock"}}}
        with pytest.raises(InvalidConnectionType) as exe_info:
            tool_resolver = ToolResolver(working_dir=None, connections=connections)
            tool_resolver._resolve_llm_connection_to_inputs(node, tool)
        assert "Connection type can not be resolved for tool" in exe_info.value.message

        # Case 4: Tool type not match the connection manager return
        tool = Tool(name="mock", type="python", inputs={"conn": InputDefinition(type=["OpenAIConnection"])})
        node = Node(
            name="mock",
            tool=tool,
            inputs={"conn": InputAssignment(value="conn_name", value_type=InputValueType.LITERAL)},
            connection="conn_name",
        )
        connections = {"conn_name": {"type": "AzureOpenAIConnection", "value": {"api_key": "mock", "api_base": "mock"}}}
        with pytest.raises(InvalidConnectionType) as exe_info:
            tool_resolver = ToolResolver(working_dir=None, connections=connections)
            tool_resolver._resolve_llm_connection_to_inputs(node, tool)
        assert "Invalid connection" in exe_info.value.message

        # Case 5: normal return
        tool = Tool(
            name="mock",
            type="python",
            inputs={"conn": InputDefinition(type=["OpenAIConnection", "AzureOpenAIConnection"])},
        )
        node = Node(
            name="mock",
            tool=tool,
            inputs={"conn": InputAssignment(value="conn_name", value_type=InputValueType.LITERAL)},
            connection="conn_name",
        )
        connections = {"conn_name": {"type": "AzureOpenAIConnection", "value": {"api_key": "mock", "api_base": "mock"}}}

        tool_resolver = ToolResolver(working_dir=None, connections=connections)
        key, conn = tool_resolver._resolve_llm_connection_to_inputs(node, tool)
        assert key == "conn"
        assert isinstance(conn, AzureOpenAIConnection)
