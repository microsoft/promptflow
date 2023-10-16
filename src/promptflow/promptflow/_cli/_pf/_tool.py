# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse
import logging
from pathlib import Path
from promptflow._sdk._constants import LOGGER_NAME


from promptflow._cli._params import logging_params
from promptflow._cli._pf._init_entry_generators import (
    ToolPackageGenerator,
    SetupGenerator,
    ToolPackageUtilsGenerator,
    InitGenerator,
)
from promptflow._cli._utils import activate_action, exception_handler


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
    tool_parser.set_defaults(action="tool")


def add_parser_init_tool(subparsers):
    """Add tool init parser to the pf tool subparsers."""
    epilog = """
Examples:

# Creating a package tool from scratch:
pf tool init --package package_tool --tool tool_name
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


def dispatch_tool_commands(args: argparse.Namespace):
    if args.sub_action == "init":
        init_tool(args)


@exception_handler("Tool init")
def init_tool(args):
    print("Creating tool from scratch...")
    if args.package:
        package_path = Path(args.package)
        package_name = package_path.stem
        script_code_path = package_path / package_name
        script_code_path.mkdir(parents=True, exist_ok=True)
        # Generate package setup.py
        SetupGenerator(package_name=package_name, tool_name=args.tool).generate_to_file(package_path / "setup.py")
        # Generate utils.py to list meta data of tools.
        ToolPackageUtilsGenerator(package_name=package_name).generate_to_file(script_code_path / "utils.py")
    else:
        script_code_path = Path(".")
    # Generate tool script
    ToolPackageGenerator(tool_name=args.tool).generate_to_file(script_code_path / f"{args.tool}.py")
    InitGenerator().generate_to_file(script_code_path / "__init__.py")
    print(f"Done. Created the tool \"{args.tool}\" in {script_code_path.resolve()}.")
