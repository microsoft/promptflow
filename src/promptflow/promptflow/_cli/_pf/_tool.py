# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse
import json
import logging
import re
import shutil
from pathlib import Path

from promptflow._cli._params import add_param_set_tool_extra_info, logging_params
from promptflow._cli._pf._init_entry_generators import (
    InitGenerator,
    ManifestGenerator,
    SetupGenerator,
    ToolPackageGenerator,
    ToolPackageUtilsGenerator,
    ToolReadmeGenerator,
)
from promptflow._cli._utils import activate_action, exception_handler, list_of_dict_to_dict
from promptflow._sdk._constants import LOGGER_NAME
from promptflow._sdk._pf_client import PFClient
from promptflow.exceptions import UserErrorException

logger = logging.getLogger(LOGGER_NAME)


def add_tool_parser(subparsers):
    """Add flow parser to the pf subparsers."""
    tool_parser = subparsers.add_parser(
        "tool",
        description="Manage tools for promptflow.",
        help="pf tool",
    )
    subparsers = tool_parser.add_subparsers()
    add_parser_init_tool(subparsers)
    add_parser_list_tool(subparsers)
    tool_parser.set_defaults(action="tool")


def add_parser_init_tool(subparsers):
    """Add tool init parser to the pf tool subparsers."""
    epilog = """
Examples:

# Creating a package tool from scratch:
pf tool init --package package_tool --tool tool_name
# Creating a package tool with extra info:
pf tool init --package package_tool --tool tool_name --set icon=<icon-path> category=<category>
# Creating a python tool from scratch:
pf tool init --tool tool_name
"""  # noqa: E501
    add_param_package = lambda parser: parser.add_argument(  # noqa: E731
        "--package", type=str, help="The package name to create."
    )
    add_param_tool = lambda parser: parser.add_argument(  # noqa: E731
        "--tool", type=str, required=True, help="The tool name to create."
    )
    add_params = [
        add_param_package,
        add_param_tool,
        add_param_set_tool_extra_info,
    ] + logging_params
    return activate_action(
        name="init",
        description="Creating a tool.",
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Initialize a tool directory.",
        action_param_name="sub_action",
    )


def add_parser_list_tool(subparsers):
    """Add tool list parser to the pf tool subparsers."""
    epilog = """
Examples:

# List all package tool in the environment:
pf tool list
# List all package tool and code tool in the flow:
pf tool list --flow flow-path
"""  # noqa: E501
    add_param_flow = lambda parser: parser.add_argument("--flow", type=str, help="the flow directory")  # noqa: E731
    add_params = [
        add_param_flow,
    ] + logging_params
    return activate_action(
        name="list",
        description="List tools.",
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="List all tools in the environment.",
        action_param_name="sub_action",
    )


def dispatch_tool_commands(args: argparse.Namespace):
    if args.sub_action == "init":
        init_tool(args)
    elif args.sub_action == "list":
        list_tool(args)


@exception_handler("Tool init")
def init_tool(args):
    # Validate package/tool name
    pattern = r"^[a-zA-Z_][a-zA-Z0-9_]*$"
    if args.package and not re.match(pattern, args.package):
        raise UserErrorException(f"The package name {args.package} is a invalid identifier.")
    if not re.match(pattern, args.tool):
        raise UserErrorException(f"The tool name {args.tool} is a invalid identifier.")
    print("Creating tool from scratch...")
    extra_info = list_of_dict_to_dict(args.extra_info)
    icon_path = extra_info.pop("icon", None)
    if icon_path:
        if not Path(icon_path).exists():
            raise UserErrorException(f"Cannot find the icon path {icon_path}.")
    if args.package:
        package_path = Path(args.package)
        package_name = package_path.stem
        script_code_path = package_path / package_name
        script_code_path.mkdir(parents=True, exist_ok=True)
        if icon_path:
            package_icon_path = package_path / "icon"
            package_icon_path.mkdir(exist_ok=True)
            dst = shutil.copy2(icon_path, package_icon_path)
            icon_path = f'Path(__file__).parent.parent / "icon" / "{Path(dst).name}"'
        # Generate package setup.py
        SetupGenerator(package_name=package_name, tool_name=args.tool).generate_to_file(package_path / "setup.py")
        # Generate manifest file
        ManifestGenerator(package_name=package_name).generate_to_file(package_path / "MANIFEST.in")
        # Generate utils.py to list meta data of tools.
        ToolPackageUtilsGenerator(package_name=package_name).generate_to_file(script_code_path / "utils.py")
        ToolReadmeGenerator(package_name=package_name, tool_name=args.tool).generate_to_file(package_path / "README.md")
    else:
        script_code_path = Path(".")
    # Generate tool script
    ToolPackageGenerator(tool_name=args.tool, icon=icon_path, extra_info=extra_info).generate_to_file(
        script_code_path / f"{args.tool}.py"
    )
    InitGenerator().generate_to_file(script_code_path / "__init__.py")
    print(f'Done. Created the tool "{args.tool}" in {script_code_path.resolve()}.')


@exception_handler("Tool list")
def list_tool(args):
    pf_client = PFClient()
    package_tools = pf_client._tools.list(args.flow)
    print(json.dumps(package_tools, indent=4))
