import pytest
from promptflow.contracts.tool import deserialize_enum, ValueType, ConnectionType, \
    InputDefinition, OutputDefinition, Tool, ToolType
from promptflow.contracts.types import Secret, PromptTemplate
from promptflow.contracts.run_info import Status
from promptflow._core.tools_manager import connections
from promptflow._sdk.entities._connection import AzureContentSafetyConnection
from enum import Enum


class TestStatus(Enum):
    Running = 1
    Preparing = 2
    Completed = 3


@pytest.mark.unittest
def test_deserialize_enum():
    assert deserialize_enum(Status, "Running") == Status.Running
    assert deserialize_enum(Status, "running") == Status.Running
    assert deserialize_enum(Status, "FAILED") == Status.Failed
    assert deserialize_enum(Status, "UNKNOWN") == "UNKNOWN"
    assert deserialize_enum(TestStatus, "Running") == "Running"


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
        ]
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
        ]
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
            ('["a", "b", "c"]', ValueType.LIST, ['a', 'b', 'c']),
            ('{"key": "value"}', ValueType.OBJECT, {'key': 'value'}),
            ('[1, 2, 3]', ValueType.OBJECT, [1, 2, 3]),
            ('{', ValueType.OBJECT, '{'),
            ([1, 2, 3], ValueType.OBJECT, [1, 2, 3]),
        ]
    )
    def test_parse(self, value, value_type, expected):
        assert value_type.parse(value) == expected

    @pytest.mark.parametrize(
        "value, value_type",
        [
            ("1", ValueType.BOOL),
            ({}, ValueType.LIST),
        ]
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
            (123, None)
        ]
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
            (123, False)
        ]
    )
    def test_is_connection_class_name(self, type_name, expected):
        assert ConnectionType.is_connection_class_name(type_name) == expected

    def test_is_connection_value(self):
        connection = connections.get("AzureContentSafetyConnection")
        # Test with a known connection class
        assert ConnectionType.is_connection_value(connection)

        # Test with an unknown connection class
        assert not ConnectionType.is_connection_value(Status)

        # Test with a connection instance
        connection_instance = AzureContentSafetyConnection("api_key", "endpoint")
        assert ConnectionType.is_connection_value(connection_instance)

        # Test with a non-connection instance
        assert not ConnectionType.is_connection_value("non_connection_instance")

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
            default='Default',
            description='Description',
            enum=['A', 'B', 'C']
        )
        serialized = input_def.serialize()
        assert serialized == {
            'type': 'string',
            'default': 'Default',
            'description': 'Description',
            'enum': ['A', 'B', 'C']
        }

        # test when len(type) > 1
        input_def = InputDefinition([ValueType.STRING, ValueType.INT])
        serialized = input_def.serialize()
        assert serialized == {
            'type': ['string', 'int']
        }

    def test_deserialize(self):
        serialized = {
            'type': 'string',
            'default': 'Default',
            'description': 'Description',
            'enum': ['A', 'B', 'C']
        }
        deserialized = InputDefinition.deserialize(serialized)
        assert deserialized.type == [ValueType.STRING]
        assert deserialized.default == 'Default'
        assert deserialized.description == 'Description'
        assert deserialized.enum == ['A', 'B', 'C']

        serialized = {
            'type': ['string', 'int']
        }
        deserialized = InputDefinition.deserialize(serialized)
        assert deserialized.type == [ValueType.STRING, ValueType.INT]
        assert deserialized.default == ''
        assert deserialized.description == ''
        assert deserialized.enum == []


@pytest.mark.unittest
class TestOutDefinition:
    def test_serialize(self):
        # test when len(type) == 1
        output_def = OutputDefinition([ValueType.STRING], description='Description', is_property=True)
        serialized = output_def.serialize()
        assert serialized == {
            'type': 'string',
            'description': 'Description',
            'is_property': True
        }

        # test when len(type) > 1
        output_def = OutputDefinition([ValueType.STRING, ValueType.INT])
        serialized = output_def.serialize()
        assert serialized == {
            'type': ['string', 'int'],
            'is_property': False
        }

    def test_deserialize(self):
        serialized = {
            'type': 'string',
            'description': 'Description',
            'is_property': True
        }
        deserialized = OutputDefinition.deserialize(serialized)
        assert deserialized.type == [ValueType.STRING]
        assert deserialized.description == 'Description'
        assert deserialized.is_property

        serialized = {
            'type': ['string', 'int'],
        }
        deserialized = OutputDefinition.deserialize(serialized)
        assert deserialized.type == [ValueType.STRING, ValueType.INT]
        assert deserialized.description == ''
        assert not deserialized.is_property


@pytest.mark.unittest
class TestTool:
    def test_tool(self):
        # Test when type is _ACTION
        tool = Tool(
            name="Test Tool",
            type=ToolType._ACTION,
            inputs={"input1": InputDefinition(type=[ValueType.STRING])},
            connection_type=["AzureContentSafetyConnection"],
            is_builtin=True,
        )

        # Test serialize method
        serialized_tool = tool.serialize()
        assert serialized_tool['name'] == "Test Tool"
        assert serialized_tool['connection_type'] == ["AzureContentSafetyConnection"]
        assert serialized_tool['is_builtin']
        with pytest.raises(KeyError):
            serialized_tool['type']

        # Test when type is not _ACTION
        tool = Tool(
            name="Test Tool",
            type=ToolType.LLM,
            inputs={"input1": InputDefinition(type=[ValueType.STRING])},
            connection_type=["AzureContentSafetyConnection"],
            is_builtin=True,
        )

        serialized_tool = tool.serialize()
        assert serialized_tool['name'] == "Test Tool"
        assert serialized_tool['connection_type'] == ["AzureContentSafetyConnection"]
        assert serialized_tool['is_builtin']
        assert serialized_tool['type'] == "llm"

        # Test deserialize method
        deserialized_tool = Tool.deserialize(serialized_tool)
        assert deserialized_tool.name == "Test Tool"
        assert deserialized_tool.connection_type == ["AzureContentSafetyConnection"]
        assert deserialized_tool.outputs == {}  # Different from defualt value "None"
        assert deserialized_tool.is_builtin
        assert deserialized_tool.stage is None
        assert deserialized_tool.type == ToolType.LLM

    def test_require_connection(self):
        tool1 = Tool(
            name="Test Tool1",
            type=ToolType.LLM,
            inputs={"input1": InputDefinition(type=[ValueType.STRING])},
        )
        assert tool1.require_connection()
        tool2 = Tool(
            name="Test Tool2",
            type=ToolType._ACTION,
            inputs={"input1": InputDefinition(type=[ValueType.STRING])},
            connection_type=["AzureContentSafetyConnection"],
        )
        assert tool2.require_connection()
        tool3 = Tool(
            name="Test Tool3",
            type=ToolType._ACTION,
            inputs={"input1": InputDefinition(type=[ValueType.STRING])},
        )
        assert not tool3.require_connection()
