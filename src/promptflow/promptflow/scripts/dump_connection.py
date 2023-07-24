"""This file is used to dump connection dataclass in module to meta json."""
import argparse
import importlib
import inspect
import json
import logging
import re
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import List, Union, get_args, get_origin

from promptflow.contracts.tool import ValueType
from promptflow.contracts.types import Secret
from promptflow.utils.utils import camel_to_snake


@dataclass
class InputDefinition:
    name: str
    displayName: str
    configValueType: str
    defaultValue: str = None
    isOptional: bool = False


def from_type(t: type):
    if t == Secret:
        return ValueType.SECRET.value.title()
    if t == str:
        return ValueType.STRING.value.title()
    logging.warning(f"Unknown type {t}, fall back to 'string'")
    return ValueType.STRING.value


@dataclass
class Connection:
    connectionCategory: str
    flowValueType: str
    connectionType: str
    module: str
    configSpecs: List[InputDefinition] = None

    def serialize(self) -> dict:
        return asdict(self, dict_factory=lambda x: {k: v for (k, v) in x if v is not None})


def resolve_annotation(anno) -> tuple:
    """Return the inner type of annotation and is_optional."""
    origin = get_origin(anno)
    is_optional = False
    # Optional[Type] is Union[Type, NoneType]
    if origin != Union:
        return anno, is_optional
    args = get_args(anno)
    is_optional = type(None) in args
    # If multiple type exists, pick the first.
    return args[0], is_optional


def dump_connection_to_meta(module):
    py_module = importlib.import_module(module)
    connections = []
    meta_list = []
    for _, obj in inspect.getmembers(py_module):
        if not inspect.isclass(obj):
            continue
        # All dataclass in the file will be collect as connection class
        if is_dataclass(obj):
            connections.append(obj)
    if not connections:
        raise Exception(f"No connection dataclass from {module!r}.")
    for connection in connections:
        params = inspect.signature(connection).parameters
        cls_name = connection.__name__
        config_specs = []
        for k, v in params.items():
            typ, is_optional = resolve_annotation(v.annotation)
            config_specs.append(
                InputDefinition(
                    name=k,
                    displayName=k.title().replace("_", " "),
                    configValueType=from_type(typ),
                    defaultValue=v.default if v.default != inspect.Parameter.empty else None,
                    isOptional=is_optional,
                )
            )
        meta_list.append(
            Connection(
                connectionCategory="CustomKeys",
                flowValueType=cls_name,
                # !!!Note: We use class name - Connection suffix as connection type, the value will be shown on UI.
                connectionType=re.sub("Connection$", "", cls_name),
                module=connection.__module__,
                configSpecs=config_specs,
            )
        )
    return meta_list


def dump_connection_from_module(module):
    meta_list = dump_connection_to_meta(module)
    for meta in meta_list:
        file_name = camel_to_snake(meta.flowValueType)
        target = Path(f"{file_name}.json")
        with open(target, "w") as f:
            f.write(json.dumps(meta.serialize(), indent=2))
        print(f"Successfully dump connection meta to {target.resolve().absolute().as_posix()}")
    logging.warning("Please double confirm each field value in the connection meta file.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--module",
        help="The module of connection dataclass definition source code file. "
        "Usage: python -m promptflow.scripts.dump_connection --module promptflow.connections",
    )
    parsed_args = parser.parse_args()
    dump_connection_from_module(parsed_args.module)
