import re
import sys
from pathlib import Path

import pytest

from promptflow._core.tools_manager import ToolLoader
from promptflow._sdk.entities import CustomConnection, CustomStrongTypeConnection
from promptflow.connections import AzureOpenAIConnection
from promptflow.contracts.flow import InputAssignment, InputValueType, Node, ToolSource, ToolSourceType
from promptflow.contracts.tool import InputDefinition, Secret, Tool, ToolType, ValueType
from promptflow.contracts.types import PromptTemplate
from promptflow.exceptions import UserErrorException
from promptflow.executor._errors import (
    ConnectionNotFound,
    InvalidConnectionType,
    InvalidSource,
    NodeInputValidationError,
    ResolveToolError,
    ValueTypeUnresolved,
)
from promptflow.executor._tool_resolver import ResolvedTool, ToolResolver

from ...utils import DATA_ROOT, FLOW_ROOT

TEST_ROOT = Path(__file__).parent.parent.parent
REQUESTS_PATH = TEST_ROOT / "test_configs/executor_api_requests"
WRONG_REQUESTS_PATH = TEST_ROOT / "test_configs/executor_wrong_requests"


class MyFirstCSTConnection(CustomStrongTypeConnection):
    api_key: Secret
    api_base: str


@pytest.mark.unittest
class TestToolResolver:
    @pytest.fixture
    def resolver(self):
        return ToolResolver(working_dir=None, connections={})

    def test_resolve_tool_by_node_with_diff_type(self, resolver, mocker):
        node = mocker.Mock(name="node", tool=None, inputs={})

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
        mocker.patch.object(
            resolver,
            "_integrate_prompt_in_package_node",
            return_value=mocker.Mock(node=node, definition=None, callable=None, init_args=None),
        )

        node.type = ToolType.PYTHON
        node.source = mocker.Mock(type=ToolSourceType.Package)
        resolver.resolve_tool_by_node(node)
        resolver._resolve_package_node.assert_called_once()

        node.type = ToolType.PYTHON
        node.source = mocker.Mock(type=ToolSourceType.Code)
        resolver.resolve_tool_by_node(node)
        resolver._resolve_script_node.assert_called_once()

        node.type = ToolType.PROMPT
        resolver.resolve_tool_by_node(node)
        resolver._resolve_prompt_node.assert_called_once()

        node.type = ToolType.LLM
        resolver.resolve_tool_by_node(node)
        resolver._resolve_llm_node.assert_called_once()

        resolver._resolve_package_node.reset_mock()
        node.type = ToolType.CUSTOM_LLM
        node.source = mocker.Mock(type=ToolSourceType.PackageWithPrompt)
        resolver.resolve_tool_by_node(node)
        resolver._resolve_package_node.assert_called_once()
        resolver._integrate_prompt_in_package_node.assert_called_once()

    def test_resolve_tool_by_node_with_invalid_type(self, resolver, mocker):
        node = mocker.Mock(name="node", tool=None, inputs={})
        node.source = mocker.Mock(type=None)

        with pytest.raises(ResolveToolError) as exec_info:
            resolver.resolve_tool_by_node(node)

        assert isinstance(exec_info.value.inner_exception, NotImplementedError)
        assert "Tool type" in exec_info.value.message

    def test_resolve_tool_by_node_with_invalid_source_type(self, resolver, mocker):
        node = mocker.Mock(name="node", tool=None, inputs={})
        node.type = ToolType.PYTHON
        node.source = mocker.Mock(type=None)

        with pytest.raises(ResolveToolError) as exec_info:
            resolver.resolve_tool_by_node(node)

        assert isinstance(exec_info.value.inner_exception, NotImplementedError)
        assert "Tool source type" in exec_info.value.message

        node.type = ToolType.CUSTOM_LLM
        node.source = mocker.Mock(type=None)
        with pytest.raises(ResolveToolError) as exec_info:
            resolver.resolve_tool_by_node(node)

        assert isinstance(exec_info.value.inner_exception, NotImplementedError)
        assert "Tool source type" in exec_info.value.message

    def test_resolve_tool_by_node_with_no_source(self, resolver, mocker):
        node = mocker.Mock(name="node", tool=None, inputs={})
        node.source = None

        with pytest.raises(ResolveToolError) as ex:
            resolver.resolve_tool_by_node(node)
        assert isinstance(ex.value.inner_exception, UserErrorException)

    def test_resolve_tool_by_node_with_no_source_path(self, resolver, mocker):
        node = mocker.Mock(name="node", tool=None, inputs={})
        node.type = ToolType.PROMPT
        node.source = mocker.Mock(type=ToolSourceType.Package, path=None)

        with pytest.raises(ResolveToolError) as exec_info:
            resolver.resolve_tool_by_node(node)

        assert isinstance(exec_info.value.inner_exception, InvalidSource)
        assert "Node source path" in exec_info.value.message

    def test_resolve_tool_by_node_with_duplicated_inputs(self, resolver, mocker):
        node = mocker.Mock(name="node", tool=None, inputs={})
        node.type = ToolType.PROMPT
        mocker.patch.object(resolver, "_load_source_content", return_value="{{template}}")

        with pytest.raises(ResolveToolError) as exec_info:
            resolver.resolve_tool_by_node(node)

        assert isinstance(exec_info.value.inner_exception, NodeInputValidationError)
        assert "These inputs are duplicated" in exec_info.value.message

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

        # Case 5: Normal case
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

    def test_resolve_llm_node(self, mocker):
        def mock_llm_api_func(prompt: PromptTemplate, **kwargs):
            from promptflow.tools.template_rendering import render_template_jinja2

            return render_template_jinja2(prompt, **kwargs)

        tool_loader = ToolLoader(working_dir=None)
        tool = Tool(name="mock", type=ToolType.LLM, inputs={"conn": InputDefinition(type=["AzureOpenAIConnection"])})
        mocker.patch.object(tool_loader, "load_tool_for_llm_node", return_value=tool)

        mocker.patch(
            "promptflow._core.tools_manager.BuiltinsManager._load_package_tool",
            return_value=(mock_llm_api_func, {"conn": AzureOpenAIConnection}),
        )

        connections = {"conn_name": {"type": "AzureOpenAIConnection", "value": {"api_key": "mock", "api_base": "mock"}}}
        tool_resolver = ToolResolver(working_dir=None, connections=connections)
        tool_resolver._tool_loader = tool_loader
        mocker.patch.object(tool_resolver, "_load_source_content", return_value="{{text}}![image]({{image}})")

        node = Node(
            name="mock",
            tool=None,
            inputs={
                "conn": InputAssignment(value="conn_name", value_type=InputValueType.LITERAL),
                "text": InputAssignment(value="Hello World!", value_type=InputValueType.LITERAL),
                "image": InputAssignment(value=str(DATA_ROOT / "test_image.jpg"), value_type=InputValueType.LITERAL),
            },
            connection="conn_name",
            provider="mock",
        )
        resolved_tool = tool_resolver._resolve_llm_node(node, convert_input_types=True)
        assert len(resolved_tool.node.inputs) == 2
        kwargs = {k: v.value for k, v in resolved_tool.node.inputs.items()}
        pattern = re.compile(r"^Hello World!!\[image\]\(Image\([a-z0-9]{8}\)\)$")
        prompt = resolved_tool.callable(**kwargs)
        assert re.match(pattern, prompt)

    def test_resolve_script_node(self, mocker):
        def mock_python_func(conn: AzureOpenAIConnection, prompt: PromptTemplate, **kwargs):
            from promptflow.tools.template_rendering import render_template_jinja2

            assert isinstance(conn, AzureOpenAIConnection)
            return render_template_jinja2(prompt, **kwargs)

        tool_loader = ToolLoader(working_dir=None)
        tool = Tool(name="mock", type=ToolType.PYTHON, inputs={"conn": InputDefinition(type=["AzureOpenAIConnection"])})
        mocker.patch.object(tool_loader, "load_tool_for_script_node", return_value=(None, mock_python_func, tool))

        connections = {"conn_name": {"type": "AzureOpenAIConnection", "value": {"api_key": "mock", "api_base": "mock"}}}
        tool_resolver = ToolResolver(working_dir=None, connections=connections)
        tool_resolver._tool_loader = tool_loader

        node = Node(
            name="mock",
            tool=None,
            inputs={
                "conn": InputAssignment(value="conn_name", value_type=InputValueType.LITERAL),
                "prompt": InputAssignment(value="{{text}}", value_type=InputValueType.LITERAL),
                "text": InputAssignment(value="Hello World!", value_type=InputValueType.LITERAL),
            },
            connection="conn_name",
            provider="mock",
        )
        resolved_tool = tool_resolver._resolve_script_node(node, convert_input_types=True)
        kwargs = {k: v.value for k, v in resolved_tool.node.inputs.items()}
        assert resolved_tool.callable(**kwargs) == "Hello World!"

    def test_resolve_package_node(self, mocker):
        def mock_package_func(prompt: PromptTemplate, **kwargs):
            from promptflow.tools.template_rendering import render_template_jinja2

            return render_template_jinja2(prompt, **kwargs)

        tool_loader = ToolLoader(working_dir=None)
        tool = Tool(name="mock", type=ToolType.PYTHON, inputs={"conn": InputDefinition(type=["AzureOpenAIConnection"])})
        mocker.patch.object(tool_loader, "load_tool_for_package_node", return_value=tool)

        mocker.patch(
            "promptflow._core.tools_manager.BuiltinsManager._load_package_tool",
            return_value=(mock_package_func, {"conn": AzureOpenAIConnection}),
        )

        connections = {"conn_name": {"type": "AzureOpenAIConnection", "value": {"api_key": "mock", "api_base": "mock"}}}
        tool_resolver = ToolResolver(working_dir=None, connections=connections)
        tool_resolver._tool_loader = tool_loader

        node = Node(
            name="mock",
            tool=None,
            inputs={
                "conn": InputAssignment(value="conn_name", value_type=InputValueType.LITERAL),
                "prompt": InputAssignment(value="{{text}}", value_type=InputValueType.LITERAL),
                "text": InputAssignment(value="Hello World!", value_type=InputValueType.LITERAL),
            },
            connection="conn_name",
            provider="mock",
        )
        resolved_tool = tool_resolver._resolve_package_node(node, convert_input_types=True)
        assert len(resolved_tool.node.inputs) == 2
        kwargs = {k: v.value for k, v in resolved_tool.node.inputs.items()}
        assert resolved_tool.callable(**kwargs) == "Hello World!"

    def test_integrate_prompt_in_package_node(self, mocker):
        def mock_package_func(prompt: PromptTemplate, **kwargs):
            from promptflow.tools.template_rendering import render_template_jinja2

            return render_template_jinja2(prompt, **kwargs)

        tool_resolver = ToolResolver(working_dir=None, connections={})
        mocker.patch.object(
            tool_resolver,
            "_load_source_content",
            return_value="{{text}}",
        )

        tool = Tool(name="mock", type=ToolType.CUSTOM_LLM, inputs={"prompt": InputDefinition(type=["PromptTemplate"])})
        node = Node(
            name="mock",
            tool=None,
            inputs={"text": InputAssignment(value="Hello World!", value_type=InputValueType.LITERAL)},
            connection="conn_name",
            provider="mock",
        )
        resolved_tool = ResolvedTool(node=node, callable=mock_package_func, definition=tool, init_args=None)
        resolved_tool = tool_resolver._integrate_prompt_in_package_node(node, resolved_tool)
        kwargs = {k: v.value for k, v in resolved_tool.node.inputs.items()}
        assert resolved_tool.callable(**kwargs) == "Hello World!"

    @pytest.mark.parametrize(
        "conn_types, expected_type",
        [
            (["MyFirstCSTConnection"], MyFirstCSTConnection),
            (["CustomConnection", "MyFirstCSTConnection"], CustomConnection),
            (["CustomConnection", "MyFirstCSTConnection", "MySecondCSTConnection"], CustomConnection),
            (["MyFirstCSTConnection", "MySecondCSTConnection"], MyFirstCSTConnection),
        ],
    )
    def test_convert_to_custom_strong_type_connection_value(self, conn_types: list[str], expected_type, mocker):
        connections = {"conn_name": {"type": "CustomConnection", "value": {"api_key": "mock", "api_base": "mock"}}}
        tool_resolver = ToolResolver(working_dir=None, connections=connections)

        node = mocker.Mock(name="node", tool=None, inputs={})
        node.type = ToolType.PYTHON
        node.source = mocker.Mock(type=ToolSourceType.Code)
        m = sys.modules[__name__]
        v = InputAssignment(value="conn_name", value_type=InputValueType.LITERAL)
        actual = tool_resolver._convert_to_custom_strong_type_connection_value("conn_name", v, node, conn_types, m)
        assert isinstance(actual, expected_type)
        assert actual.api_base == "mock"

    def test_load_source(self):
        # Create a mock Node object with a valid source path
        node = Node(name="mock", tool=None, inputs={}, source=ToolSource())
        node.source.path = "./script_with_special_character/script_with_special_character.py"

        resolver = ToolResolver(FLOW_ROOT)

        result = resolver._load_source_content(node)
        assert "https://www.bing.com/\ue000\ue001/" in result

    @pytest.mark.parametrize(
        "source",
        [
            None,
            ToolSource(path=None),  # Then will try to read one directory.
            ToolSource(path=""),  # Then will try to read one directory.
            ToolSource(path="NotExistPath.py"),
        ],
    )
    def test_load_source_error(self, source):
        # Create a mock Node object with a valid source path
        node = Node(name="mock", tool=None, inputs={}, source=source)
        resolver = ToolResolver(FLOW_ROOT)

        with pytest.raises(InvalidSource) as _:
            resolver._load_source_content(node)
