import argparse
import json
import os
import sys
from pathlib import Path

from promptflow.utils.generate_tool_meta_utils import generate_prompt_meta_dict, generate_python_meta_dict
from promptflow.core.tools_manager import collect_package_tools


def infer_tool_type_by_file(f: Path, tool_type):
    suffix = Path(f).suffix
    if suffix == ".py":
        return "python"
    elif suffix == ".jinja2":
        return tool_type or "prompt"
    else:
        raise ValueError(f"Unsupported file type {suffix}.")


def update_tools(target, tool_meta, is_package_tool=False):
    if not os.path.exists(target):
        tools = {"package": {}, "code": {}}
    else:
        with open(target, "r") as f:
            tools = json.load(f)
    if is_package_tool:
        tools["package"].update(tool_meta)
    else:
        tools["code"][tool_meta["source"]] = tool_meta
    with open(target, "w") as f:
        json.dump(tools, f, indent=2)


def collect_script_tool(args, working_dir):
    tool_type = infer_tool_type_by_file(args.file, args.type)
    sys.path.insert(0, str(working_dir))
    args.file = Path(args.file).as_posix()
    with open(working_dir / args.file, "r") as f:
        content = f.read()
    name = Path(args.file).stem
    if tool_type == "python":
        meta_dict = generate_python_meta_dict(name, content, args.file)
    elif tool_type == "llm":
        meta_dict = generate_prompt_meta_dict(name, content, source=args.file)
    elif tool_type == "prompt":
        meta_dict = generate_prompt_meta_dict(name, content, prompt_only=True, source=args.file)
    else:
        raise ValueError(f"Unsupported tool type {args.type}.")
    useless_variables = ["outputs", "name"]
    for v in useless_variables:
        if v in meta_dict:
            meta_dict.pop(v)
    return meta_dict


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generate meta for a tool.")
    parser.add_argument("--list", help="List all the tools in current packages.", action="store_true")
    parser.add_argument("--file", "-f", help="Path to the tool script file.", type=str)
    parser.add_argument("--working-dir", "-wd", help="Flow working directory of the tool.", default=None)
    parser.add_argument("--type", "-t", help="Type of the tool, python or llm or prompt.")
    parser.add_argument("--output", "-o", help="Path to the output tool json file.", required=True)
    parser.add_argument("--mode", "-m", choices=["append", "output"], default="append")
    args = parser.parse_args()
    working_dir = Path(args.working_dir or Path.cwd()).absolute().resolve()
    if args.list:
        tools = collect_package_tools()
        for identifier in tools:
            print(f"Collected {identifier}")
    else:
        tools = collect_script_tool(args, working_dir)

    args.output = Path(args.output)
    if not args.output.is_absolute():
        args.output = working_dir / args.output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.mode == "output":
        with open(args.output, "w") as f:
            json.dump(tools, f, indent=2)
        print(f"Meta file generated at '{args.output}'.")
    else:
        update_tools(args.output, tools, is_package_tool=args.list)
        print(f"Meta file updated at '{args.output}'.")
