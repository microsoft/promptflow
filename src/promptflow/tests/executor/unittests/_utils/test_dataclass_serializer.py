import pytest
from datetime import datetime
from typing import Dict, List
from promptflow._utils.dataclass_serializer import \
    get_type, serialize, deserialize_dataclass, deserialize_value, assertEqual
from promptflow.contracts.run_info import RunInfo, Status
from promptflow.storage.run_records import NodeRunRecord


@pytest.mark.unittest
@pytest.mark.parametrize(
    "type_input, expected",
    [
        (NodeRunRecord, NodeRunRecord),
        (List[int], List[int]),
        (Dict[str, int], Dict[str, int]),
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
    serialized_run_info = serialize(node_run_info)
    deserialized_run_info = deserialize_dataclass(RunInfo, serialized_run_info)
    assert deserialized_run_info == node_run_info


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
@pytest.mark.parametrize(
    "a, b, are_equal",
    [
        # Test with identical dicts
        ({'key1': 'value1', 'key2': 'value2'}, {'key1': 'value1', 'key2': 'value2'}, True),
        # Test with non-identical dicts
        ({'key1': 'value1', 'key2': 'value2'}, {'key1': 'value1', 'key3': 'value3'}, False),
        # Test with identical lists
        (['item1', 'item2'], ['item1', 'item2'], True),
        # Test with non-identical lists
        (['item1', 'item2'], ['item1', 'item3'], False),
        # Test with other types
        (1, 1, True),
        (1, 2, False),
        ('string', 'string', True),
        ('string1', 'string2', False),
    ]
)
def test_assertEqual(a, b, are_equal):
    if are_equal:
        assertEqual(a, b)
    else:
        with pytest.raises(AssertionError):
            assertEqual(a, b)
