# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Type, TypeVar

from promptflow._core.generator_proxy import GeneratorProxy
from promptflow.contracts.multimedia import Image
from promptflow.contracts.tool import ConnectionType

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


def serialize(value: object, remove_null=False, pfbytes_file_reference_encoder=None) -> dict:
    if isinstance(value, datetime):
        return value.isoformat() + "Z"
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, list):
        return [serialize(v, remove_null, pfbytes_file_reference_encoder) for v in value]
    if isinstance(value, GeneratorProxy):
        return [serialize(v, remove_null, pfbytes_file_reference_encoder) for v in value.items]
    #  Note that custom connection check should before dict check
    if ConnectionType.is_connection_value(value):
        return ConnectionType.serialize_conn(value)
    if isinstance(value, dict):
        return {
            k: serialize(v, remove_null, pfbytes_file_reference_encoder)
            for k, v in value.items()
        }
    if isinstance(value, Image):
        return value.serialize(pfbytes_file_reference_encoder)
    if is_dataclass(value):
        if hasattr(value, "serialize"):
            result = value.serialize()
        else:
            result = {
                f.name: serialize(getattr(value, f.name), remove_null, pfbytes_file_reference_encoder)
                for f in fields(value)
            }
        if not remove_null:
            return result
        null_keys = [k for k, v in result.items() if v is None]
        for k in null_keys:
            result.pop(k)
        return result
    try:
        from pydantic import BaseModel

        if isinstance(value, BaseModel):  # Handle pydantic model, which is used in langchain
            return value.dict()
    except ImportError:
        # Ignore ImportError if pydantic is not installed
        pass
    return value


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
