import pytest
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, List
from promptflow._core.generator_proxy import GeneratorProxy
from promptflow._utils.dataclass_serializer import \
    get_type, serialize, deserialize_dataclass, deserialize_value, assertEqual
from promptflow.contracts.run_info import RunInfo, Status
from promptflow._core.connection_manager import ConnectionManager
from promptflow.storage.run_records import NodeRunRecord
from unittest.mock import patch, Mock
import sys


def get_connection_dict():
    return {
        "azure_open_ai_connection": {
            "type": "AzureOpenAIConnection",
            "value": {
                "api_key": "<azure-openai-key>",
                "api_base": "https://gpt-test-eus.openai.azure.com/",
                "api_type": "azure",
                "api_version": "2023-07-01-preview",
            },
        },
        "custom_connection": {
            "type": "CustomConnection",
            "value": {
                "api_key": "<your-key>",
                "url": "https://api.bing.microsoft.com/v7.0/search",
            },
            "module": "promptflow.connections",
            "secret_keys": ["api_key"],
        },
    }


@pytest.mark.unittest
@pytest.mark.parametrize(
    "type_input, expected",
    [
        (NodeRunRecord, NodeRunRecord),
        ([NodeRunRecord], List[NodeRunRecord]),
        (dict(a=NodeRunRecord), Dict[str, NodeRunRecord]),
        (int, int),
        (str, str),
    ]
)
def test_get_type(type_input, expected):
    assert get_type(type_input) == expected


@pytest.mark.unittest
def test_serialize_dataclass():
    start_time = datetime(2023, 9, 4)
    end_time = datetime(2023, 9, 4)
    node_run_info = RunInfo(
        node=None,
        run_id=None,
        flow_run_id=None,
        status=Status.Completed,
        inputs=None,
        output=None,
        metrics=None,
        error=None,
        parent_run_id=None,
        start_time=start_time,
        end_time=end_time,
        index=0,
    )
    node_record = NodeRunRecord.from_run_info(node_run_info)
    serialized_run_info = serialize(node_run_info)
    deserialized_run_info = deserialize_value(serialized_run_info, RunInfo)
    assert deserialized_run_info == node_run_info
    assert serialize(node_record) == node_record.serialize()


@pytest.mark.unittest
@pytest.mark.parametrize(
    "value, value_type",
    [
        (datetime(2023, 9, 4), datetime),
        (Status.Completed, Status),
        ([1, 2, 3], List[int]),
        ({"a": 1, "b": 2}, Dict[str, int]),
        (1, int),
        ("a", str),
    ]
)
def test_serialize_value(value, value_type):
    assert deserialize_value(serialize(value), value_type) == value


@pytest.mark.unittest
def test_serialize_remove_null():
    value = {"a": 1, "b": None}
    value_type = Dict[str, int]
    assert deserialize_value(serialize(value, remove_null=True), value_type) == {"a": 1, "b": None}

    @dataclass
    class DummyDataClass:
        name: str
        age: int
    serialized_dataclass = serialize(DummyDataClass("Dummy", None), remove_null=True)
    assert serialize(serialized_dataclass, remove_null=True) == {'name': 'Dummy'}

    new_connection = get_connection_dict()
    connection_manager = ConnectionManager(new_connection)
    assert serialize(connection_manager.get("azure_open_ai_connection"), remove_null=True) == "azure_open_ai_connection"

    def generator():
        for i in range(3):
            yield i
    g = GeneratorProxy(generator())
    next(g)
    assert serialize(g, remove_null=True) == [0]


@pytest.mark.unittest
@patch.dict('sys.modules', {'pydantic': None})
def test_import_pydantic_error():
    # mock pydantic is not installed
    class DummyClass:
        def __init__(self, name, age):
            self.name = name
            self.age = age
    dummy = DummyClass('Test', 20)
    assert serialize(dummy) == dummy


@pytest.mark.unittest
@patch.dict('sys.modules', {'pydantic': Mock()})
def test_import_pydantic():
    # mock pydantic is installed
    class MockBaseModel:
        def dict(self):
            return {"key": "value"}

    mock_value = MockBaseModel()
    sys.modules['pydantic'].BaseModel = MockBaseModel
    assert serialize(mock_value) == mock_value.dict()
    assert serialize(123) == 123


@pytest.mark.unittest
def test_deserialize_dataclass():
    # test when cls is not dataclass
    with pytest.raises(ValueError):
        deserialize_dataclass(int, 1)
    # test when data is not a dict
    with pytest.raises(ValueError):
        deserialize_dataclass(NodeRunRecord, "NodeRunRecord")

    @dataclass
    class DummyDataClassWithDefault:
        name: str = "Default Name"
        age: int = 0
    # test deserialize dataclass with default value
    data = {"age": 25}
    obj = deserialize_dataclass(DummyDataClassWithDefault, data)
    assert obj.name == "Default Name"
    assert obj.age == 25


@pytest.mark.unittest
def test_deserialize_value():
    # test when field_type is not type
    assert deserialize_value(1, 2) == 1
    # test when field_type is subclass of Enum
    assert deserialize_value(Status.Completed, Status) == Status.Completed
    # test with none datetime
    assert deserialize_value(None, datetime) is None
    # test with datetime without z
    date_str = "2022-01-01T00:00:00"
    assert deserialize_value(date_str, datetime) == datetime.fromisoformat(date_str)


@pytest.mark.unittest
@pytest.mark.parametrize(
    "a, b, path, are_equal",
    [
        # Test with identical dicts
        ({'key1': 'value1', 'key2': 'value2'}, {'key1': 'value1', 'key2': 'value2'}, \
            "unittests/_utils/test_dataclass_serializer", True),
        # Test with non-identical dicts
        ({'key1': 'value1', 'key2': 'value2'}, {'key1': 'value1', 'key3': 'value3'}, \
            "unittests/_utils/test_dataclass_serializer", False),
        # Test with identical lists
        (['item1', 'item2'], ['item1', 'item2'], "", True),
        # Test with non-identical lists
        (['item1', 'item2'], ['item1', 'item3'], "", False),
        # Test with other types
        (1, 1, "", True),
        (1, 2, "", False),
        ('string', 'string', "", True),
        ('string1', 'string2', "", False),
    ]
)
def test_assertEqual(a, b, path, are_equal):
    if are_equal:
        assertEqual(a, b, path)
    else:
        with pytest.raises(AssertionError):
            assertEqual(a, b, path)
