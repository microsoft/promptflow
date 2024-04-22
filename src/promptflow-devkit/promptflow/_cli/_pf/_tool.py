# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

from promptflow._cli._params import add_param_set_tool_extra_info, base_params
from promptflow._cli._pf._init_entry_generators import (
    InitGenerator,
    SetupGenerator,
    ToolPackageGenerator,
    ToolPackageUtilsGenerator,
    ToolReadmeGenerator,
)
from promptflow._cli._utils import activate_action, list_of_dict_to_dict
from promptflow._sdk._constants import DEFAULT_ENCODING
from promptflow._sdk._pf_client import PFClient
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow.exceptions import UserErrorException

logger = get_cli_sdk_logger()


def add_tool_parser(subparsers):
    """Add flow parser to the pf subparsers."""
    tool_parser = subparsers.add_parser(
        "tool",
        description="Manage tools for promptflow.",
        help="Manage tools.",
    )
    subparsers = tool_parser.add_subparsers()
    add_parser_init_tool(subparsers)
    add_parser_list_tool(subparsers)
    add_parser_validate_tool(subparsers)
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
    ] + base_params
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
    ] + base_params
    return activate_action(
        name="list",
        description="List tools.",
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="List all tools in the environment.",
        action_param_name="sub_action",
    )


def add_parser_validate_tool(subparsers):
    """Add tool list parser to the pf tool subparsers."""
    epilog = """
Examples:

# Validate single function tool:
pf tool validate -–source <package_name>.<module_name>.<tool_function>
# Validate all tool in a package tool:
pf tool validate -–source <package_name>
# Validate tools in a python script:
pf tool validate --source <path_to_tool_script>
"""  # noqa: E501

    def add_param_source(parser):
        parser.add_argument("--source", type=str, help="The tool source to be used.", required=True)

    return activate_action(
        name="validate",
        description="Validate tool.",
        epilog=epilog,
        add_params=[
            add_param_source,
        ],
        subparsers=subparsers,
        help_message="Validate tool. Will raise error if it is not valid.",
        action_param_name="sub_action",
    )


def dispatch_tool_commands(args: argparse.Namespace):
    if args.sub_action == "init":
        init_tool(args)
    elif args.sub_action == "list":
        list_tool(args)
    elif args.sub_action == "validate":
        validate_tool(args)


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
    if icon_path and not Path(icon_path).exists():
        raise UserErrorException(f"Cannot find the icon path {icon_path}.")
    if args.package:
        package_path = Path(args.package)
        package_name = package_path.stem
        script_code_path = package_path / package_name
        script_code_path.mkdir(parents=True, exist_ok=True)

        # Generate manifest file
        manifest_file = package_path / "MANIFEST.in"
        manifest_file.touch(exist_ok=True)
        with open(manifest_file, "r") as f:
            manifest_contents = [line.strip() for line in f.readlines()]

        if icon_path:
            package_icon_path = package_path / "icons"
            package_icon_path.mkdir(exist_ok=True)
            dst = shutil.copy2(icon_path, package_icon_path)
            icon_path = f'Path(__file__).parent.parent / "icons" / "{Path(dst).name}"'

            icon_manifest = f"include {package_name}/icons"
            if icon_manifest not in manifest_contents:
                manifest_contents.append(icon_manifest)

        with open(manifest_file, "w", encoding=DEFAULT_ENCODING) as f:
            f.writelines("\n".join(set(manifest_contents)))
        # Generate package setup.py
        SetupGenerator(package_name=package_name, tool_name=args.tool).generate_to_file(package_path / "setup.py")
        # Generate utils.py to list meta data of tools.
        ToolPackageUtilsGenerator(package_name=package_name).generate_to_file(script_code_path / "utils.py")
        ToolReadmeGenerator(package_name=package_name, tool_name=args.tool).generate_to_file(package_path / "README.md")
    else:
        script_code_path = Path(".")
        if icon_path:
            icon_path = f'"{Path(icon_path).as_posix()}"'
    # Generate tool script
    ToolPackageGenerator(tool_name=args.tool, icon=icon_path, extra_info=extra_info).generate_to_file(
        script_code_path / f"{args.tool}.py"
    )
    InitGenerator().generate_to_file(script_code_path / "__init__.py")
    print(f'Done. Created the tool "{args.tool}" in {script_code_path.resolve()}.')


def list_tool(args):
    pf_client = PFClient()
    package_tools = pf_client._tools.list(args.flow)
    print(json.dumps(package_tools, indent=4))


def validate_tool(args):
    import importlib

    pf_client = PFClient()
    try:
        __import__(args.source)
        source = importlib.import_module(args.source)
        logger.debug(f"The source {args.source} is used as a package to validate.")
    except ImportError:
        try:
            module_name, func_name = args.source.rsplit(".", 1)
            module = importlib.import_module(module_name)
            source = getattr(module, func_name)
            logger.debug(f"The source {args.source} is used as a function to validate.")
        except Exception:
            if not Path(args.source).exists():
                raise UserErrorException("Invalid source to validate tools.")
            logger.debug(f"The source {args.source} is used as a script to validate.")
            source = args.source
    validation_result = pf_client._tools.validate(source)
    print(repr(validation_result))
    if not validation_result.passed:
        sys.exit(1)
