# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse
import logging
import shutil
from pathlib import Path
from promptflow._sdk._constants import LOGGER_NAME, PROMPT_FLOW_DIR_NAME
from promptflow._sdk._pf_client import PFClient

from promptflow._cli._params import (
    add_param_tool,
    add_param_package,
    logging_params
)
from promptflow._cli._pf._init_entry_generators import (
    ToolPackageGenerator,
    SetupGenerator,
)
from promptflow._cli._utils import activate_action


logger = logging.getLogger(LOGGER_NAME)


def add_tool_parser(subparsers):
    """Add flow parser to the pf subparsers."""
    flow_parser = subparsers.add_parser(
        "tool",
        description="Manage tools for promptflow.",
        help="pf tool",
    )
    flow_parser.set_defaults(action="tool")


def add_parser_init_tool(subparsers):
    """Add tool init parser to the pf tool subparsers."""
    # TODO create python tool by exist code
    # TODO create package tool by exist code
    epilog = """
Examples:

# Creating a package tool from scratch:
pf tool init --package package_tool --tool tool_name
# Creating a python tool from scratch:
pf tool init --tool tool_name
"""  # noqa: E501
    add_params = [
        add_param_package,
        add_param_tool,
    ] + logging_params
    activate_action(
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
    elif args.sub_action == "list":
        list_tool(args)


def init_tool(args):
    # TODO create from existing code
    print("Creating tool from scratch...")
    _init_tool_by_template(args.package, args.tool)


def _init_tool_by_template(package, tool):
    if package:
        package_path = Path(package)
        package_name = package_path.stem
        package_path.mkdir(parents=True, exist_ok=True)
        script_code_path = package_path / package_path.stem
        script_code_path.mkdir(parents=True, exist_ok=True)
        template_path = Path(__file__).parent.parent / "data" / "package_tool"
        (script_code_path / "__init__.py").touch(exist_ok=True)
        shutil.copy2(template_path / "utils.py", script_code_path / "utils.py")
        SetupGenerator(package_name=package_name, tool_name=tool).generate_to_file(package_path / "setup.py")
    else:
        script_code_path = Path(".")
    ToolPackageGenerator(tool_name=tool).generate_to_file(script_code_path / f"{tool}.py")


def list_tool(args):
    pass
