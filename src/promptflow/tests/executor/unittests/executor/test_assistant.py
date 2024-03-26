import pytest

from promptflow.contracts.flow import ToolSourceType
from promptflow.contracts.tool import ToolType
from promptflow.executor import FlowExecutor
from promptflow.executor._assistant_tool_invoker import AssistantToolResolver
from promptflow.executor._errors import InvalidAssistantTool, ResolveToolError

from ...utils import WRONG_FLOW_ROOT, get_yaml_file


@pytest.mark.unittest
@pytest.mark.usefixtures("use_secrets_config_file", "dev_connections")
class TestAssistant:
    @pytest.mark.parametrize(
        "flow_folder, exception_class, error_message",
        [
            (
                "assistant_package_tool_wrong_source_type",
                ResolveToolError,
                (
                    "Tool source type 'package1' is not supported in assistant node 'assistant'. "
                    "Please make sure the assistant definition is correct."
                ),
            ),
            (
                "assistant_package_tool_wrong_tool",
                ResolveToolError,
                (
                    "Package tool 'hello.world' is not found in the current environment. "
                    "All available package tools are: []."
                ),
            ),
            (
                "assistant_python_tool_wrong_path",
                ResolveToolError,
                ("Load tool failed for node 'assistant'. Tool file './hello.py' can not be found."),
            ),
        ],
    )
    def test_assistant_tool_resolve_exception(self, dev_connections, flow_folder, exception_class, error_message):

        with pytest.raises(exception_class) as e:
            executor = FlowExecutor.create(get_yaml_file(flow_folder, WRONG_FLOW_ROOT), dev_connections)
            executor.exec_line({})
        assert error_message in str(e.value)


@pytest.mark.unittest
@pytest.mark.usefixtures
class TestAssistantToolResolver:
    def test_resolve_python_tool(self):
        data = {
            "type": "function",
            "source": {"path": "dummy_assistant.py", "type": "code"},
            "tool_type": "python",
            "predefined_inputs": {"connection": "my_aoai_connection"},
        }
        tool = AssistantToolResolver.from_dict(data, "dummy_assistant")
        assert tool.type == "function"
        assert tool.tool_type == ToolType.PYTHON
        assert tool.source.path == "dummy_assistant.py"
        assert tool.source.type == ToolSourceType.Code
        assert tool.predefined_inputs == {"connection": "my_aoai_connection"}

    def test_resolve_package_tool(self):
        data = {
            "type": "function",
            "source": {"tool": "hello.world", "type": "package"},
            "tool_type": "python",
            "predefined_inputs": {"connection": "my_aoai_connection"},
        }
        tool = AssistantToolResolver.from_dict(data, "dummy_assistant")
        assert tool.type == "function"
        assert tool.tool_type == ToolType.PYTHON
        assert tool.source.tool == "hello.world"
        assert tool.source.type == ToolSourceType.Package
        assert tool.predefined_inputs == {"connection": "my_aoai_connection"}

    def test_type_invalid(self):
        data = {
            "type": "type11",
            "source": {"tool": "hello.world", "type": "package"},
            "tool_type": "python",
            "predefined_inputs": {"connection": "my_aoai_connection"},
        }
        with pytest.raises(InvalidAssistantTool) as e:
            AssistantToolResolver.from_dict(data, "dummy_assistant")
        assert (
            "Unsupported assistant tool's type in node <node_name> : type11. "
            "Please make sure the type is restricted within "
            "['code_interpreter', 'function', 'retrieval']." in str(e.value)
        )

        data = {
            "source": {"tool": "hello.world", "type": "package"},
            "tool_type": "python",
            "predefined_inputs": {"connection": "my_aoai_connection"},
        }
        with pytest.raises(InvalidAssistantTool) as e:
            AssistantToolResolver.from_dict(data, "dummy_assistant")
        assert (
            "Unsupported assistant tool's type in node <node_name> : None. "
            "Please make sure the type is restricted within "
            "['code_interpreter', 'function', 'retrieval']." in str(e.value)
        )

    def test_invalid_source(self):
        data = {"type": "function", "tool_type": "python", "predefined_inputs": {"connection": "my_aoai_connection"}}
        with pytest.raises(InvalidAssistantTool) as e:
            AssistantToolResolver.from_dict(data, "dummy_assistant")
        assert (
            "The 'source' property is missing in the assistant node 'dummy_assistant'. "
            "Please make sure the assistant definition is correct."
        ) in str(e.value)

        data = {
            "type": "function",
            "source": {"type": "code"},
            "tool_type": "python",
            "predefined_inputs": {"connection": "my_aoai_connection"},
        }
        with pytest.raises(InvalidAssistantTool) as e:
            AssistantToolResolver.from_dict(data, "dummy_assistant")
        assert (
            "The 'path' property is missing in 'source' of the assistant python tool in node 'dummy_assistant'. "
            "Please make sure the assistant definition is correct."
        ) in str(e.value)

        data = {
            "type": "function",
            "source": {"path": "", "type": "code"},
            "tool_type": "python",
            "predefined_inputs": {"connection": "my_aoai_connection"},
        }
        with pytest.raises(InvalidAssistantTool) as e:
            AssistantToolResolver.from_dict(data, "dummy_assistant")
        assert (
            "The 'path' property is missing in 'source' of the assistant python tool in node 'dummy_assistant'. "
            "Please make sure the assistant definition is correct."
        ) in str(e.value)

        data = {
            "type": "function",
            "source": {"path": "hello.py", "type": "code11"},
            "tool_type": "python",
            "predefined_inputs": {"connection": "my_aoai_connection"},
        }
        with pytest.raises(InvalidAssistantTool) as e:
            AssistantToolResolver.from_dict(data, "dummy_assistant")
        assert (
            "Tool source type 'code11' is not supported in assistant node "
            "'dummy_assistant'. Please make sure the assistant definition is correct."
        ) in str(e.value)

    def test_invalid_tool_type(self):
        data = {
            "type": "function",
            "source": {"path": "hello.py", "type": "code"},
            "tool_type": "python11",
            "predefined_inputs": {"connection": "my_aoai_connection"},
        }
        with pytest.raises(InvalidAssistantTool) as e:
            AssistantToolResolver.from_dict(data, "dummy_assistant")
        assert (
            "The 'tool_type' property is missing or invalid in assistant node 'dummy_assistant'. "
            "Please make sure the assistant definition is correct."
        ) in str(e.value)
