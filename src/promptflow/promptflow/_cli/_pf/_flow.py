# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse
import importlib
import json
import logging
import os
import shutil
import webbrowser
from pathlib import Path

from promptflow._cli._params import (
    add_param_entry,
    add_param_environment_variables,
    add_param_flow_name,
    add_param_function,
    add_param_inputs,
    add_param_prompt_template,
    add_param_source,
    add_param_yes,
    add_parser_build,
    logging_params,
)
from promptflow._cli._pf._init_entry_generators import (
    FlowDAGGenerator,
    ToolMetaGenerator,
    ToolPyGenerator,
    copy_extra_files,
)
from promptflow._cli._pf._run import exception_handler
from promptflow._cli._utils import activate_action, confirm, inject_sys_path, list_of_dict_to_dict
from promptflow._sdk._constants import LOGGER_NAME, PROMPT_FLOW_DIR_NAME
from promptflow._sdk._pf_client import PFClient

logger = logging.getLogger(LOGGER_NAME)


def add_flow_parser(subparsers):
    """Add flow parser to the pf subparsers."""
    flow_parser = subparsers.add_parser(
        "flow",
        description="Manage flows for promptflow.",
        help="pf flow",
    )
    flow_subparsers = flow_parser.add_subparsers()
    add_parser_init_flow(flow_subparsers)
    add_parser_test_flow(flow_subparsers)
    add_parser_serve_flow(flow_subparsers)
    add_parser_build(flow_subparsers, "flow")
    add_parser_validate_flow(flow_subparsers)
    flow_parser.set_defaults(action="flow")


def dispatch_flow_commands(args: argparse.Namespace):
    if args.sub_action == "init":
        init_flow(args)
    elif args.sub_action == "test":
        test_flow(args)
    elif args.sub_action == "serve":
        if (hasattr(args, "verbose") and args.verbose) or (hasattr(args, "debug") and args.debug):
            pass
        else:
            for handler in logging.getLogger(LOGGER_NAME).handlers:
                handler.setLevel(logging.INFO)
        serve_flow(args)
    elif args.sub_action == "build":
        build_flow(args)
    elif args.sub_action == "validate":
        validate_flow(args)


def add_parser_init_flow(subparsers):
    """Add flow create parser to the pf flow subparsers."""
    epilog = """
Examples:

# Creating a flow folder with code/prompts and yaml definitions of the flow:
pf flow init --flow my-awesome-flow
# Creating an eval prompt flow:
pf flow init --flow my-awesome-flow --type evaluation
# Creating a flow in existing folder
pf flow init --flow intent_copilot --entry intent.py --function extract_intent --prompt-template prompt_template=tpl.jinja2
"""  # noqa: E501
    add_param_type = lambda parser: parser.add_argument(  # noqa: E731
        "--type",
        type=str,
        choices=["standard", "evaluation", "chat"],
        help="The initialized flow type.",
        default="standard",
    )

    add_params = [
        add_param_type,
        add_param_yes,
        add_param_flow_name,
        add_param_entry,
        add_param_function,
        add_param_prompt_template,
    ] + logging_params
    activate_action(
        name="init",
        description="Creating a flow folder with code/prompts and yaml definitions of the flow.",
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Initialize a prompt flow directory.",
        action_param_name="sub_action",
    )


def add_parser_serve_flow(subparsers):
    """Add flow serve parser to the pf flow subparsers."""
    epilog = """
Examples:

# Serve flow as an endpoint:
pf flow serve --source <path_to_flow>
# Serve flow as an endpoint with specific port and host:
pf flow serve --source <path_to_flow> --port 8080 --host localhost --environment-variables key1="`${my_connection.api_key}" key2="value2"
"""  # noqa: E501
    add_param_port = lambda parser: parser.add_argument(  # noqa: E731
        "--port", type=int, default=8080, help="The port on which endpoint to run."
    )
    add_param_host = lambda parser: parser.add_argument(  # noqa: E731
        "--host", type=str, default="localhost", help="The host of endpoint."
    )
    add_param_static_folder = lambda parser: parser.add_argument(  # noqa: E731
        "--static_folder", type=str, help=argparse.SUPPRESS
    )
    activate_action(
        name="serve",
        description="Serving a flow as an endpoint.",
        epilog=epilog,
        add_params=[
            add_param_source,
            add_param_port,
            add_param_host,
            add_param_static_folder,
            add_param_environment_variables,
        ]
        + logging_params,
        subparsers=subparsers,
        help_message="Serving a flow as an endpoint.",
        action_param_name="sub_action",
    )


def add_parser_validate_flow(subparsers):
    """Add flow validate parser to the pf flow subparsers."""
    epilog = """
Examples:

# Validate flow
pf flow validate --source <path_to_flow>
"""  # noqa: E501
    activate_action(
        name="validate",
        description="Validate a flow and generate flow.tools.json for the flow.",
        epilog=epilog,
        add_params=[
            add_param_source,
        ],
        subparsers=subparsers,
        help_message="Validate a flow. Will raise error if the flow is not valid.",
        action_param_name="sub_action",
    )


def add_parser_test_flow(subparsers):
    """Add flow test parser to the pf flow subparsers."""
    epilog = """
Examples:

# Test the flow:
pf flow test --flow my-awesome-flow
# Test the flow with inputs:
pf flow test --flow my-awesome-flow --inputs key1=val1 key2=val2
# Test the flow with specified variant node:
pf flow test --flow my-awesome-flow --variant ${node_name.variant_name}
# Test the single node in the flow:
pf flow test --flow my-awesome-flow --node node_name
# Chat in the flow:
pf flow test --flow my-awesome-flow --node node_name --interactive
"""  # noqa: E501
    add_param_flow = lambda parser: parser.add_argument(  # noqa: E731
        "--flow", type=str, required=True, help="the flow directory to test."
    )
    add_param_node = lambda parser: parser.add_argument(  # noqa: E731
        "--node", type=str, help="the node name in the flow need to be tested."
    )
    add_param_variant = lambda parser: parser.add_argument(  # noqa: E731
        "--variant", type=str, help="Node & variant name in format of ${node_name.variant_name}."
    )
    add_param_interactive = lambda parser: parser.add_argument(  # noqa: E731
        "--interactive", action="store_true", help="start a interactive chat session for chat flow."
    )
    add_param_input = lambda parser: parser.add_argument("--input", type=str, help=argparse.SUPPRESS)  # noqa: E731

    add_params = [
        add_param_flow,
        add_param_node,
        add_param_variant,
        add_param_interactive,
        add_param_input,
        add_param_inputs,
        add_param_environment_variables,
    ] + logging_params
    activate_action(
        name="test",
        description="Test the flow.",
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Test the prompt flow or flow node.",
        action_param_name="sub_action",
    )


def init_flow(args):
    if any([args.entry, args.prompt_template]):
        print("Creating flow from existing folder...")
        prompt_tpl = {}
        if args.prompt_template:
            for _dct in args.prompt_template:
                prompt_tpl.update(**_dct)
        _init_existing_flow(args.flow, args.entry, args.function, prompt_tpl)
    else:
        # Create an example flow
        print("Creating flow from scratch...")
        _init_flow_by_template(args.flow, args.type, args.yes)


def _init_existing_flow(flow_name, entry=None, function=None, prompt_params: dict = None):
    flow_path = Path(flow_name).resolve()
    if not function:
        logger.error("--function must be specified when --entry is specified.")
        return
    if not flow_path.exists():
        logger.error(f"{flow_path.resolve()} must exist when --entry specified.")
        return
    print(f"Change working directory to .. {flow_path.resolve()}")
    os.chdir(flow_path)
    entry = Path(entry).resolve()
    if not entry.exists():
        logger.error(f"{entry} must exist.")
        return
    with inject_sys_path(flow_path):
        # import function object
        function_obj = getattr(importlib.import_module(entry.stem), function)
    # Create tool.py
    tool_py = f"{function}_tool.py"
    python_tool = ToolPyGenerator(entry, function, function_obj)
    tools = ToolMetaGenerator(tool_py, function, function_obj, prompt_params)

    python_tool_inputs = [arg.name for arg in python_tool.tool_arg_list]
    for tool_input in tools.prompt_params.keys():
        if tool_input not in python_tool_inputs:
            raise ValueError(f"Template parameter {tool_input} doesn't find in python function arguments.")

    python_tool.generate_to_file(tool_py)
    # Create .promptflow and flow.tools.json
    meta_dir = flow_path / PROMPT_FLOW_DIR_NAME
    meta_dir.mkdir(parents=True, exist_ok=True)
    tools.generate_to_file(meta_dir / "flow.tools.json")
    # Create flow.dag.yaml
    FlowDAGGenerator(tool_py, function, function_obj, prompt_params).generate_to_file("flow.dag.yaml")
    copy_extra_files(flow_path=flow_path, extra_files=[".gitignore"])
    print(f"Done. Generated flow in folder: {flow_path.resolve()}.")


def _init_flow_by_template(flow_name, flow_type, overwrite=False):
    flow_path = Path(flow_name)
    if flow_path.exists():
        if not flow_path.is_dir():
            logger.error(f"{flow_path.resolve()} is not a folder.")
            return
        answer = (
            overwrite
            if overwrite
            else confirm("The flow folder already exists, do you want to create the flow in this existing folder?")
        )
        if not answer:
            print("The 'pf init' command has been cancelled.")
            return
    flow_path.mkdir(parents=True, exist_ok=True)
    example_flow_path = Path(__file__).parent.parent / "data" / f"{flow_type}_flow"
    for item in list(example_flow_path.iterdir()):
        target = flow_path / item.name
        action = "Overwriting" if target.exists() else "Creating"
        if item.is_file():
            print(f"{action} {item.name}...")
            shutil.copy2(item, target)
        else:
            print(f"{action} {item.name} folder...")
            shutil.copytree(item, target, dirs_exist_ok=True)
    copy_extra_files(flow_path=flow_path, extra_files=["requirements.txt", ".gitignore"])

    print(f"Done. Created {flow_type} flow folder: {flow_path.resolve()}.")
    if flow_type == "chat":
        flow_test_args = "--interactive"
        print(
            "The generated chat flow is requiring a connection named open_ai_connection, "
            "please follow the steps in README.md to create if you haven't done that."
        )
    else:
        flow_test_args = f"--input {os.path.join(flow_name, 'data.jsonl')}"
    flow_test_command = f"pf flow test --flow {flow_name} " + flow_test_args
    print(f"You can execute this command to test the flow, {flow_test_command}")


@exception_handler("Flow test")
def test_flow(args):
    from promptflow._sdk._load_functions import load_flow
    from promptflow._sdk._utils import parse_variant
    from promptflow._sdk.operations._test_submitter import TestSubmitter

    pf_client = PFClient()

    if args.environment_variables:
        environment_variables = list_of_dict_to_dict(args.environment_variables)
    else:
        environment_variables = {}
    inputs = {}
    if args.input:
        from promptflow._utils.load_data import load_data

        if args.input and not args.input.endswith(".jsonl"):
            raise ValueError("Only support jsonl file as input.")
        inputs = load_data(local_path=args.input)[0]
    if args.inputs:
        inputs.update(list_of_dict_to_dict(args.inputs))

    if args.interactive:
        pf_client.flows._chat(
            flow=args.flow,
            inputs=inputs,
            environment_variables=environment_variables,
            variant=args.variant,
            show_step_output=args.verbose,
        )
    else:
        result = pf_client.flows._test(
            flow=args.flow,
            inputs=inputs,
            environment_variables=environment_variables,
            variant=args.variant,
            node=args.node,
            allow_generator_output=False,
        )
        # Dump flow/node test info
        flow = load_flow(args.flow)
        if args.node:
            TestSubmitter._dump_result(flow_folder=flow.code, node_result=result, prefix=f"flow-{args.node}.node")
        else:
            if args.variant:
                tuning_node, node_variant = parse_variant(args.variant)
                prefix = f"flow-{tuning_node}-{node_variant}"
            else:
                prefix = "flow"
            TestSubmitter._dump_result(flow_folder=flow.code, flow_result=result, prefix=prefix)

        TestSubmitter._raise_error_when_test_failed(result, show_trace=args.node is not None)
        # Print flow/node test result
        if isinstance(result.output, dict):
            print(json.dumps(result.output, indent=4))
        else:
            print(result.output)


def serve_flow(args):
    logger.info("Start serve model: %s", args.source)
    # Set environment variable for local test
    source = Path(args.source)
    os.environ["PROMPTFLOW_PROJECT_PATH"] = source.absolute().as_posix()
    from promptflow._sdk._serving.app import create_app

    static_folder = args.static_folder
    if static_folder:
        static_folder = Path(static_folder).absolute().as_posix()
    logger.info(
        "Start promptflow server with port %s",
        args.port,
    )
    # Change working directory to model dir
    print(f"Change working directory to model dir {source}")
    os.chdir(source)
    app = create_app(
        static_folder=static_folder, environment_variables=list_of_dict_to_dict(args.environment_variables)
    )
    target = f"http://{args.host}:{args.port}"
    print(f"Opening browser {target}...")
    webbrowser.open(target)
    # Debug is not supported for now as debug will rerun command, and we changed working directory.
    app.run(port=args.port, host=args.host)
    logger.info("Promptflow app ended")


def build_flow(args):
    """
    i. `pf flow build --source <flow_folder> --output <output_folder> --variant <variant>`
    ii. `pf flow build --source <flow_folder> --format docker --output <output_folder> --variant <variant>`
    iii. `pf flow build --source <flow_folder> --format executable --output <output_folder> --variant <variant>`

    # default to resolve variant and update flow.dag.yaml, support this in case customer want to keep the
    variants for continuous development
    # we can delay this before receiving specific customer request
    v. `pf flow build --source <flow_folder> --output <output_folder> --keep-variants`

    output structure:
    flow/
    .connections/
    Dockerfile|executable.exe
    ...
    """
    pf_client = PFClient()

    pf_client.flows.build(
        flow=args.source,
        output=args.output,
        format=args.format,
        variant=args.variant,
        flow_only=args.flow_only,
    )
    print(
        f"Exported flow to {Path(args.output).absolute().as_posix()}.\n"
        f"please check {Path(args.output).joinpath('README.md').absolute().as_posix()} "
        f"for how to use it."
    )


def validate_flow(args):
    pf_client = PFClient()

    validation_result = pf_client.flows.validate(
        flow=args.source,
    )
    print(repr(validation_result))
    if not validation_result.passed:
        exit(1)
    else:
        exit(0)
