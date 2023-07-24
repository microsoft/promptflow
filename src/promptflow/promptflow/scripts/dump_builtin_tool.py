import argparse
import importlib
import inspect
from pathlib import Path

from promptflow.core.tool import dump
from promptflow.utils.context_utils import _change_working_dir, inject_sys_path
from promptflow.utils.generate_tool_meta_utils import is_tool


def dump_tool_to_meta(name, py_module, description=None):
    tool = []
    for _, obj in inspect.getmembers(py_module):
        if is_tool(obj):
            tool.append(obj)
        elif not inspect.isclass(obj):
            continue
        for _, cls_obj in inspect.getmembers(obj, inspect.isfunction):
            if is_tool(cls_obj):
                tool.append(cls_obj)
    if len(tool) != 1:
        raise Exception(f"Expected 1 but collected {len(tool)} tool(s) from {py_module!r}.")
    return dump(tool[0], name, description)


def dump_tool_from_path(name, description, file_path):
    working_dir = file_path.parent
    with _change_working_dir(working_dir, mkdir=False), inject_sys_path(working_dir):
        py_module = importlib.import_module(file_path.stem)
    meta = dump_tool_to_meta(name, py_module, description=description)
    target = file_path.parent / f"{name}.json"
    with open(target, "w") as f:
        f.write(meta)
    print(f"Successfully dump tool {name!r} meta to {target.resolve().as_posix()}")


def dump_tool_from_module(name, description, module):
    py_module = importlib.import_module(module)
    meta = dump_tool_to_meta(name, py_module, description=description)
    target = Path(f"{name}.json")
    with open(target, "w") as f:
        f.write(meta)
    print(f"Successfully dump tool {name!r} meta to {target.resolve().as_posix()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--name",
        "-n",
        required=True,
        help="The name of the tool",
    )
    parser.add_argument(
        "--path",
        "-p",
        help="The path of python source code file",
    )
    parser.add_argument(
        "--module",
        help="The module of tool source code file, exclusive with --path",
    )
    parser.add_argument(
        "--description",
        "-d",
        required=True,
        help="The description of the tool",
    )

    parsed_args = parser.parse_args()

    if parsed_args.path:
        path = Path(parsed_args.path).resolve()
        if not path.exists():
            raise Exception(f"The given file path {path!r} not exists.")
        dump_tool_from_path(parsed_args.name, parsed_args.description, path)
    elif parsed_args.module:
        dump_tool_from_module(parsed_args.name, parsed_args.description, parsed_args.module)
