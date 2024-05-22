from dataclasses import dataclass
from datetime import datetime
from enum import Enum

import pytest

from promptflow.tracing._utils import get_input_names_for_prompt_template, get_prompt_param_name_from_func, serialize
from promptflow.tracing.contracts.iterator_proxy import IteratorProxy


class DummyEnum(Enum):
    ITEM = "Item"


@pytest.mark.unittest
@pytest.mark.parametrize(
    "value, expected",
    [
        (datetime(2023, 9, 4), "2023-09-04T00:00:00Z"),
        (DummyEnum.ITEM, "Item"),
        ([1, 2, 3], [1, 2, 3]),
        ({"a": 1, "b": 2}, {"a": 1, "b": 2}),
        (1, 1),
        ("a", "a"),
    ],
)
def test_serialize(value, expected):
    assert serialize(value) == expected


@pytest.mark.unittest
def test_serialize_dataclass():
    @dataclass
    class DummyDataClass:
        item: str
        optional_item: str = None

    @dataclass
    class DataClassWithSerialize:
        item: str

        def serialize(self):
            return f"The item is {self.item}."

    assert serialize(DummyDataClass("text", "text")) == {"item": "text", "optional_item": "text"}
    assert serialize(DummyDataClass("text")) == {"item": "text", "optional_item": None}
    assert serialize(DummyDataClass("text"), remove_null=True) == {"item": "text"}
    assert serialize(DataClassWithSerialize("text")) == "The item is text."


@pytest.mark.unittest
def test_serialize_with_serialization_funcs():
    class DummyClass:
        def __init__(self, item):
            self.item = item

        def serialize(self):
            return {"item": self.item}

    serialization_funcs = {DummyClass: DummyClass.serialize}
    assert serialize(DummyClass("test"), serialization_funcs=serialization_funcs) == {"item": "test"}


@pytest.mark.unittest
def test_serialize_generator():
    def generator():
        for i in range(3):
            yield i

    g = IteratorProxy(generator())
    next(g), next(g), next(g)
    assert serialize(g) == [0, 1, 2]


@pytest.mark.unittest
def test_get_input_names_for_prompt_template():
    assert get_input_names_for_prompt_template("{{input}}") == []


@pytest.mark.unittest
def test_get_prompt_param_name_from_func():
    def dummy_func(input: str):
        pass

    assert get_prompt_param_name_from_func(dummy_func) is None
