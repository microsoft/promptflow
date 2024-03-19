import pytest

from promptflow.executor import FlowExecutor
from promptflow.executor._errors import ResolveToolError

from ...utils import WRONG_FLOW_ROOT, get_yaml_file


@pytest.mark.unittest
@pytest.mark.usefixtures("use_secrets_config_file", "dev_connections")
class TestAssistant:
    @pytest.mark.parametrize(
        "flow_folder, exception_class, error_message",
        [
            (
                "assistant_without_source",
                ResolveToolError,
                ("Node assistant does has tools without source defined in assistant definition."),
            ),
            (
                "assistant_python_tool_no_path",
                ResolveToolError,
                (
                    "The 'path' property is missing in 'source' of the assistant python tool in node 'assistant'. "
                    "Please make sure the assistant definition is correct."
                ),
            ),
            (
                "assistant_package_tool_no_tool",
                ResolveToolError,
                (
                    "The 'tool' property is missing in 'source' of the assistant package tool in node 'assistant'. "
                    "Please make sure the assistant definition is correct."
                ),
            ),
            (
                "assistant_python_tool_wrong_tool_type",
                ResolveToolError,
                (
                    "Tool type python1 is not supported yet in assistant definition for node 'assistant'. "
                    "Please make sure the assistant definition is correct."
                ),
            ),
            (
                "assistant_package_tool_wrong_source_type",
                ResolveToolError,
                (
                    "Tool source type package1 is not supported yet in assistant definition for node 'assistant'. "
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
