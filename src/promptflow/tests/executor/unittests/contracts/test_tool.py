from enum import Enum
from typing import Any, Callable, NewType, Optional, Tuple, TypeVar, Union

import pytest

from promptflow._core.tools_manager import connections
from promptflow._sdk.entities import CustomStrongTypeConnection
from promptflow._sdk.entities._connection import AzureContentSafetyConnection
from promptflow.contracts.multimedia import Image
from promptflow.contracts.run_info import Status
from promptflow.contracts.tool import (
    AssistantDefinition,
    ConnectionType,
    InputDefinition,
    OutputDefinition,
    Tool,
    ToolType,
    ValueType,
    _deserialize_enum,
)
from promptflow.contracts.types import FilePath, PromptTemplate, Secret


class MyConnection(CustomStrongTypeConnection):
    pass


my_connection = MyConnection(name="my_connection", secrets={"key": "value"})


def some_function():
    pass


class TestStatus(Enum):
    Running = 1
    Preparing = 2
    Completed = 3


@pytest.mark.unittest
@pytest.mark.parametrize(
    "enum, value, expected",
    [
        (Status, "Running", Status.Running),
        (Status, "running", Status.Running),
        (Status, "FAILED", Status.Failed),
        (Status, "UNKNOWN", "UNKNOWN"),
        (TestStatus, "Running", "Running"),
    ],
)
def test_deserialize_enum(enum, value, expected):
    assert _deserialize_enum(enum, value) == expected


@pytest.mark.unittest
class TestValueType:
    @pytest.mark.parametrize(
        "value, expected",
        [
            (1, ValueType.INT),
            (1.0, ValueType.DOUBLE),
            (True, ValueType.BOOL),
            ("string", ValueType.STRING),
            ([], ValueType.LIST),
            ({}, ValueType.OBJECT),
            (Secret("secret"), ValueType.SECRET),
            (PromptTemplate("prompt"), ValueType.PROMPT_TEMPLATE),
            (FilePath("file_path"), ValueType.FILE_PATH),
            (AssistantDefinition("model", "instructions", []), ValueType.ASSISTANT_DEFINITION),
        ],
    )
    def test_from_value(self, value, expected):
        assert ValueType.from_value(value) == expected

    @pytest.mark.parametrize(
        "value, expected",
        [
            (int, ValueType.INT),
            (float, ValueType.DOUBLE),
            (bool, ValueType.BOOL),
            (str, ValueType.STRING),
            (list, ValueType.LIST),
            (dict, ValueType.OBJECT),
            (Secret, ValueType.SECRET),
            (PromptTemplate, ValueType.PROMPT_TEMPLATE),
            (FilePath, ValueType.FILE_PATH),
            (Image, ValueType.IMAGE),
            (AssistantDefinition, ValueType.ASSISTANT_DEFINITION),
        ],
    )
    def test_from_type(self, value, expected):
        assert ValueType.from_type(value) == expected

    @pytest.mark.parametrize(
        "value, value_type, expected",
        [
            ("1", ValueType.INT, 1),
            ("1.0", ValueType.DOUBLE, 1.0),
            ("true", ValueType.BOOL, True),
            ("false", ValueType.BOOL, False),
            (True, ValueType.BOOL, True),
            (123, ValueType.STRING, "123"),
            ('["a", "b", "c"]', ValueType.LIST, ["a", "b", "c"]),
            ('{"key": "value"}', ValueType.OBJECT, {"key": "value"}),
            ("[1, 2, 3]", ValueType.OBJECT, [1, 2, 3]),
            ("{", ValueType.OBJECT, "{"),
            ([1, 2, 3], ValueType.OBJECT, [1, 2, 3]),
        ],
    )
    def test_parse(self, value, value_type, expected):
        assert value_type.parse(value) == expected

    @pytest.mark.parametrize(
        "value, value_type",
        [
            ("1", ValueType.BOOL),
            ({}, ValueType.LIST),
        ],
    )
    def test_parse_error(self, value, value_type):
        with pytest.raises(ValueError):
            value_type.parse(value)


@pytest.mark.unittest
class TestConnectionType:
    @pytest.mark.parametrize(
        "type_name, expected",
        [
            ("AzureContentSafetyConnection", connections.get("AzureContentSafetyConnection")),
            ("AzureOpenAIConnection", connections.get("AzureOpenAIConnection")),
            ("_Connection", connections.get("_Connection")),
            ("unknown", None),
            (123, None),
        ],
    )
    def test_get_connection_class(self, type_name, expected):
        assert ConnectionType.get_connection_class(type_name) == expected

    @pytest.mark.parametrize(
        "type_name, expected",
        [
            ("AzureContentSafetyConnection", True),
            ("AzureOpenAIConnection", True),
            ("_Connection", True),
            ("unknown", False),
            (123, False),
        ],
    )
    def test_is_connection_class_name(self, type_name, expected):
        assert ConnectionType.is_connection_class_name(type_name) == expected

    @pytest.mark.parametrize(
        "value, expected",
        [
            (connections.get("AzureContentSafetyConnection"), True),
            (AzureContentSafetyConnection("api_key", "endpoint"), True),
            (Status, False),
            (ConnectionType.is_connection_value("non_connection_instance"), False),
        ],
    )
    def test_is_connection_value(self, value, expected):
        assert ConnectionType.is_connection_value(value) == expected

    @pytest.mark.parametrize(
        "val, expected_res",
        [
            (my_connection, True),
            (MyConnection, True),
            (list, False),
            # (list[str], False), # Python 3.9
            # (list[int], False),
            ([1, 2, 3], False),
            (float, False),
            (int, False),
            (5, False),
            (str, False),
            (some_function, False),
            (Union[str, int], False),
            # ((int | str), False), # Python 3.10
            (tuple, False),
            # (tuple[str, int], False), # Python 3.9
            (Tuple[int, ...], False),
            # (dict[str, Any], False), # Python 3.9
            ({"test1": [1, 2, 3], "test2": [4, 5, 6], "test3": [7, 8, 9]}, False),
            (Any, False),
            (None, False),
            (Optional[str], False),
            (TypeVar("T"), False),
            (TypeVar, False),
            (Callable, False),
            (Callable[..., Any], False),
            (NewType("MyType", int), False),
        ],
    )
    def test_is_custom_strong_type(self, val, expected_res):
        assert ConnectionType.is_custom_strong_type(val) == expected_res

    def test_serialize_conn(self):
        assert ConnectionType.serialize_conn(AzureContentSafetyConnection) == "ABCMeta"

        connection_instance = AzureContentSafetyConnection("api_key", "endpoint")
        assert ConnectionType.serialize_conn(connection_instance) == "AzureContentSafetyConnection"

        with pytest.raises(ValueError):
            ConnectionType.serialize_conn("non_connection_instance")


@pytest.mark.unittest
class TestInputDefinition:
    def test_serialize(self):
        # test when len(type) == 1
        input_def = InputDefinition(
            [ValueType.STRING],
            default="Default",
            description="Description",
            enum=["A", "B", "C"],
            custom_type=["customtype"],
        )
        serialized = input_def.serialize()
        assert serialized == {
            "type": "string",
            "default": "Default",
            "description": "Description",
            "enum": ["A", "B", "C"],
            "custom_type": ["customtype"],
        }

        # test when len(type) > 1
        input_def = InputDefinition([ValueType.STRING, ValueType.INT])
        serialized = input_def.serialize()
        assert serialized == {"type": ["string", "int"]}

    def test_deserialize(self):
        serialized = {"type": "string", "default": "Default", "description": "Description", "enum": ["A", "B", "C"]}
        deserialized = InputDefinition.deserialize(serialized)
        assert deserialized.type == [ValueType.STRING]
        assert deserialized.default == "Default"
        assert deserialized.description == "Description"
        assert deserialized.enum == ["A", "B", "C"]

        serialized = {"type": ["string", "int"]}
        deserialized = InputDefinition.deserialize(serialized)
        assert deserialized.type == [ValueType.STRING, ValueType.INT]
        assert deserialized.default == ""
        assert deserialized.description == ""
        assert deserialized.enum == []


@pytest.mark.unittest
class TestOutDefinition:
    @pytest.mark.parametrize(
        "value, expected",
        [
            (
                OutputDefinition([ValueType.STRING], description="Description", is_property=True),
                {"type": "string", "description": "Description", "is_property": True},
            ),
            (OutputDefinition([ValueType.STRING, ValueType.INT]), {"type": ["string", "int"], "is_property": False}),
        ],
    )
    def test_serialize(self, value, expected):
        assert value.serialize() == expected

    @pytest.mark.parametrize(
        "value, expected",
        [
            (
                {"type": "string", "description": "Description", "is_property": True},
                OutputDefinition([ValueType.STRING], description="Description", is_property=True),
            ),
            ({"type": ["string", "int"]}, OutputDefinition([ValueType.STRING, ValueType.INT])),
        ],
    )
    def test_deserialize(self, value, expected):
        assert OutputDefinition.deserialize(value) == expected


@pytest.mark.unittest
class TestTool:
    @pytest.mark.parametrize(
        "tool_type, expected_keys",
        [
            (ToolType._ACTION, ["name", "description", "enable_kwargs"]),
            (ToolType.LLM, ["name", "type", "inputs", "description", "enable_kwargs"]),
        ],
    )
    def test_serialize_tool(self, tool_type, expected_keys):
        tool = Tool(name="test_tool", type=tool_type, inputs={}, outputs={}, description="description")
        serialized_tool = tool.serialize()
        assert set(serialized_tool.keys()) == set(expected_keys)

    def test_deserialize_tool(self):
        data = {
            "name": "test_tool",
            "type": "LLM",
            "inputs": {"input1": {"type": "ValueType1"}},
        }
        tool = Tool.deserialize(data)
        assert tool.name == data["name"]
        assert tool.type == ToolType[data["type"]]
        assert "input1" in tool.inputs

    @pytest.mark.parametrize(
        "tooltype, connection_type, expected",
        [
            (ToolType.LLM, None, True),
            (ToolType._ACTION, ["AzureContentSafetyConnection"], True),
            (ToolType._ACTION, None, False),
        ],
    )
    def test_require_connection(self, tooltype, connection_type, expected):
        tool = Tool(name="Test Tool", type=tooltype, inputs={}, connection_type=connection_type)
        assert tool._require_connection() == expected
