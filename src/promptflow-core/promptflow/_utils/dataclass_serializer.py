# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Type, TypeVar

from promptflow._constants import DEFAULT_OUTPUT_NAME

T = TypeVar("T")


def get_type(obj: type):
    if is_dataclass(obj):
        return obj
    if isinstance(obj, list):
        return List[get_type(obj[0])]
    if isinstance(obj, dict):
        return Dict[str, get_type(obj[list(obj.keys())[0]])]
    return obj


def deserialize_dataclass(cls: Type[T], data: dict) -> T:
    if not is_dataclass(cls):
        raise ValueError(f"{cls} is not a dataclass")
    if not isinstance(data, dict):
        raise ValueError(f"{data} is not a dict")
    kwargs = {}
    for field in fields(cls):
        if field.name not in data:
            kwargs[field.name] = field.default
            continue
        field_type = get_type(field.type)
        kwargs[field.name] = deserialize_value(data[field.name], field_type)
    return cls(**kwargs)


def deserialize_value(obj, field_type):
    if not isinstance(field_type, type):
        return obj

    if is_dataclass(field_type):
        return deserialize_dataclass(field_type, obj)

    if issubclass(field_type, Enum):
        return field_type(obj)

    if issubclass(field_type, datetime) and obj is not None:
        # Remove Z/z at the end of the string.
        if obj.endswith("Z") or obj.endswith("z"):
            return datetime.fromisoformat(obj[:-1])
        return datetime.fromisoformat(obj)

    return obj


def assertEqual(a: dict, b: dict, path: str = ""):
    if isinstance(a, dict):
        assert isinstance(b, dict), f"{path}: {type(a)} != {type(b)}"
        assert set(a.keys()) == set(b.keys()), f"{path}: {set(a.keys())} != {set(b.keys())}"
        for key in a.keys():
            assertEqual(a[key], b[key], path + "." + key)
    elif isinstance(a, list):
        assert isinstance(b, list), f"{path}: {type(a)} != {type(b)}"
        assert len(a) == len(b), f"{path}: {len(a)} != {len(b)}"
        for i in range(len(a)):
            assertEqual(a[i], b[i], path + f"[{i}]")
    else:
        assert a == b, f"{path}: {a} != {b}"


def convert_eager_flow_output_to_dict(value: Any):
    """
    Convert the output of eager flow to a dict. Since the output of eager flow
    may not be a dict, we need to convert it to a dict in batch mode.

    Examples:
    1. If the output is a dict, return it directly:
        value = {"output": 1} -> {"output": 1}
    2. If the output is a dataclass, convert it to a dict:
        value = SampleDataClass(output=1) -> {"output": 1}
    3. If the output is not a dict or dataclass, convert it to a dict by adding a key "output":
        value = 1 -> {"output": 1}
    """

    if isinstance(value, dict):
        return value
    elif is_dataclass(value):
        return {f.name: getattr(value, f.name) for f in fields(value)}
    else:
        return {DEFAULT_OUTPUT_NAME: value}


def convert_dataclass_to_dict(value: Any):
    if is_dataclass(value):
        return {f.name: getattr(value, f.name) for f in fields(value)}
    else:
        return value
