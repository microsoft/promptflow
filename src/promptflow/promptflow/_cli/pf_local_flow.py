# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import argparse
import contextlib
import importlib
import json
import os
import shutil
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from promptflow._cli._params import (
    add_param_entry,
    add_param_environment_variables,
    add_param_flow_name,
    add_param_function,
    add_param_prompt_template,
    add_param_source,
    add_param_yes,
    add_parser_export,
)
from promptflow._cli.pf_init_entry_generators import FlowDAGGenerator, ToolMetaGenerator, ToolPyGenerator
from promptflow._cli.pf_logger_factory import _LoggerFactory
from promptflow._cli.utils import (
    activate_action,
    confirm,
    get_migration_secret_from_args,
    inject_sys_path,
    list_of_dict_to_dict,
)
from promptflow.sdk._pf_client import PFClient

logger = _LoggerFactory.get_logger()


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
    add_parser_export(flow_subparsers, "flow")
    flow_parser.set_defaults(action="flow")


def dispatch_flow_commands(args: argparse.Namespace):
    if args.sub_action == "init":
        init_flow(args)
    elif args.sub_action == "test":
        test_flow(args)
    elif args.sub_action == "serve":
        serve_flow(args)
    elif args.sub_action == "export":
        export_flow(args)


def add_parser_init_flow(subparsers):
    """Add flow create parser to the pf flow subparsers."""
    epilog = """
Examples:

# Creating a flow folder with code/prompts and yaml definitions of the flow:
pf flow init --flow my-awesome-flow
# Creating an eval prompt flow:
pf flow init --flow my-awesome-flow --type evaluation
# Creating a flow in existing folder
pf flow init --flow intent_copilot --entry intent.py --function extract_intent --prompt-template prompt_template=tpl.md
"""  # noqa: E501
    init_parser = subparsers.add_parser(
        "init",
        description="Creating a flow folder with code/prompts and yaml definitions of the flow.",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="Initialize a prompt flow directory.",
    )

    add_params = [add_param_yes, add_param_flow_name, add_param_entry, add_param_function, add_param_prompt_template]
    for add_param_func in add_params:
        add_param_func(init_parser)

    init_parser.add_argument(
        "--type",
        type=str,
        choices=["standard", "evaluation", "chat"],
        help="The initialized flow type.",
        default="standard",
    )
    init_parser.set_defaults(sub_action="init")


def add_parser_serve_flow(subparsers):
    """Add flow serve parser to the pf flow subparsers."""
    epilog = """  # noqa: E501
Examples:

# Serve flow as an endpoint:
pf flow serve --source <path_to_flow>
# Serve flow as an endpoint with specific port and host:
pf flow serve --source <path_to_flow> --port 8080 --host localhost --environment-variables key1="`${my_connection.api_key}" key2="value2"
"""
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
        ],
        subparsers=subparsers,
        action_param_name="sub_action",
    )


def add_parser_test_flow(subparsers):
    """Add flow test parser to the pf flow subparsers."""
    epilog = """
Examples:

# Test the flow:
pf flow test --flow my-awesome-flow
# Test the flow with single line from input file:
pf flow test --flow my-awesome-flow --input input_file.jsonl
# Test the flow with specified variant node:
pf flow test --flow my-awesome-flow --variant ${node_name。variant_name}
# Test the single node in the flow:
pf flow test --flow my-awesome-flow --node node_name
# Debug the single node in the flow:
pf flow test --flow my-awesome-flow --node node_name --debug
# Chat in the flow:
pf flow test --flow my-awesome-flow --node node_name --interactive
"""  # noqa: E501
    test_parser = subparsers.add_parser(
        "test",
        description="Test the flow.",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="Test the prompt flow or flow node in local.",
    )

    test_parser.add_argument("--flow", type=str, required=True, help="the flow directory to test.")
    test_parser.add_argument(
        "--input",
        type=str,
        help="the input file path. Note that we accept jsonl file only for now. If not configured, "
        "the default value in the dag will be used as input",
    )
    test_parser.add_argument("--node", type=str, help="the node name in the flow need to be tested.")
    test_parser.add_argument("--variant", type=str, help="Node & variant name in format of ${node_name.variant_name}.")
    test_parser.add_argument("--debug", action="store_true", help="debug the single node in the flow.")
    test_parser.add_argument(
        "--interactive", action="store_true", help="start a interactive chat session for chat flow."
    )
    test_parser.add_argument(
        "--verbose", action="store_true", help="displays the output for each step in the chat flow."
    )
    test_parser.set_defaults(sub_action="test")


def init_flow(args):
    if any([args.entry, args.prompt_template]):
        logger.info("Creating flow from existing folder...")
        prompt_tpl = {}
        if args.prompt_template:
            for _dct in args.prompt_template:
                prompt_tpl.update(**_dct)
        _init_existing_flow(args.flow, args.entry, args.function, prompt_tpl)
    else:
        # Create an example flow
        logger.info("Creating flow from scratch...")
        _init_flow_by_template(args.flow, args.type, args.yes)


def _init_existing_flow(flow_name, entry=None, function=None, prompt_params: dict = None):
    flow_path = Path(flow_name).resolve()
    if not function:
        logger.error("--function must be specified when --entry is specified.")
        return
    if not flow_path.exists():
        logger.error(f"{flow_path.resolve()} must exist when --entry specified.")
        return
    logger.info(f"Change working directory to .. {flow_path.resolve()}")
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
    ToolPyGenerator(entry, function, function_obj).generate_to_file(tool_py)
    # Create .promptflow and flow.tools.json
    meta_dir = flow_path / ".promptflow"
    meta_dir.mkdir(parents=True, exist_ok=True)
    ToolMetaGenerator(tool_py, function, function_obj, prompt_params).generate_to_file(meta_dir / "flow.tools.json")
    # Create flow.dag.yaml
    FlowDAGGenerator(tool_py, function, function_obj, prompt_params).generate_to_file("flow.dag.yaml")
    logger.info(f"Done. Generated flow in folder: {flow_path.resolve()}.")


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
            logger.info("The 'pf init' command has been cancelled.")
            return
    flow_path.mkdir(parents=True, exist_ok=True)
    example_flow_path = Path(__file__).parent / "data" / f"{flow_type}_flow"
    for item in list(example_flow_path.iterdir()):
        target = flow_path / item.name
        action = "Overwriting" if target.exists() else "Creating"
        if item.is_file():
            logger.info(f"{action} {item.name}...")
            shutil.copy2(item, target)
        else:
            logger.info(f"{action} {item.name} folder...")
            shutil.copytree(item, target, dirs_exist_ok=True)
    requirements_path = Path(__file__).parent / "data" / "entry_flow" / "requirements_txt"
    logger.info("Creating requirements.txt...")
    shutil.copy2(requirements_path, flow_path / "requirements.txt")

    logger.info(f"Done. Created {flow_type} flow folder: {flow_path.resolve()}.")
    flow_test_args = "--interactive" if flow_type == "chat" else f"--input {os.path.join(flow_name, 'data.jsonl')}"
    flow_test_command = f"pf flow test --flow {flow_name} " + flow_test_args
    logger.info(f"You can execute this command to test the flow, {flow_test_command}")


def _get_connections_in_flow(flow):
    referenced_connections = {}
    referenced_connection_names = set()
    for node in flow.nodes:
        if node.connection is not None:
            referenced_connection_names.add(node.connection)
        connection_inputs = _get_tool_connection_inputs(node, flow.tools)
        for connection_input in connection_inputs:
            if connection_input is not None and connection_input in node.inputs:
                referenced_connection_names.add(node.inputs[connection_input].value)
    _client = PFClient()
    for connection in referenced_connection_names:
        connection_obj = _client.connections.get(connection, with_secrets=True)
        if connection_obj:
            referenced_connections[connection] = connection_obj.to_execution_connection_dict()
    return referenced_connections


def _get_tool_connection_inputs(node, tools):
    connection_inputs = []
    for tool in tools:
        if tool.name == node.tool and node.inputs is not None:
            for input_name, input_def in tool.inputs.items():
                if len(input_def.type) == 1 and input_def.type[0].endswith("Connection"):
                    connection_inputs.append(input_name)
    return connection_inputs


@contextlib.contextmanager
def _get_input(flow, node_name=None, input_path=None, additional_input=None):
    if input_path and not additional_input:
        yield input_path
        return

    inputs = {}
    if input_path:
        with open(input_path, "r") as f:
            inputs = json.load(f)
    else:
        from promptflow.contracts.flow import InputValueType

        # Using default value of inputs as flow input
        if node_name:
            node = next(filter(lambda item: item.name == node_name, flow.nodes), None)
            if not node:
                raise RuntimeError(f"Cannot find {node_name} in the flow.")
            for name, value in node.inputs.items():
                if value.value_type == InputValueType.FLOW_INPUT:
                    input_value = flow.inputs[value.value].default
                elif value.value_type == InputValueType.NODE_REFERENCE:
                    continue
                else:
                    input_value = value.value
                if input_value is not None:
                    inputs[f"{value.prefix}{name}"] = input_value
        else:
            for name, value in flow.inputs.items():
                if value.default is not None:
                    inputs[name] = value.default
    _, input_file = tempfile.mkstemp(suffix=".jsonl")
    if additional_input:
        inputs.update(additional_input)
    with open(input_file, "w") as f:
        f.write(json.dumps(inputs))
    yield input_file
    shutil.rmtree(input_file, ignore_errors=True)


def _dump_result(result, path, prefix):
    if result.detail:
        with open(Path(path) / f"{prefix}.detail.json", "w") as f:
            json.dump(result.detail, f, indent=2)
    if result.metrics:
        with open(Path(path) / f"{prefix}.metrics.json", "w") as f:
            json.dump(result.metrics, f, indent=2)
    if result.output:
        with open(Path(path) / f"{prefix}.output.json", "w") as f:
            json.dump(result.output, f, indent=2)


def _chat_flow(flow, executable_flow, connections, input_path, verbose=False):
    from colorama import Fore, init

    @contextmanager
    def add_prefix():
        write = sys.stdout.write

        def prefix_output(*args, **kwargs):
            if args[0].strip():
                write(f"{Fore.LIGHTBLUE_EX}[{executable_flow.name}]: ")
            write(*args, **kwargs)

        sys.stdout.write = prefix_output
        yield
        sys.stdout.write = write

    def disable_streaming_handler():
        from logging import ERROR, StreamHandler

        from promptflow.utils.logger_utils import bulk_logger, flow_logger

        loggers = [logger, flow_logger, bulk_logger]
        for logger_ in loggers:
            for log_handler in logger_.handlers:
                if isinstance(log_handler, StreamHandler):
                    log_handler.setLevel(ERROR)

    init(autoreset=True)
    chat_history = []
    log_path = Path(flow.code) / ".promptflow" / "chat.log"
    run_id = datetime.now().strftime("run_%Y%m%d%H%M%S")
    input_name = next(filter(lambda key: executable_flow.inputs[key].is_chat_input, executable_flow.inputs.keys()))
    output_name = next(filter(lambda key: executable_flow.outputs[key].is_chat_output, executable_flow.outputs.keys()))

    while True:
        try:
            print(f"{Fore.GREEN}User: ", end="")
            input_value = input()
            if not input_value.strip():
                continue
        except (KeyError, EOFError):
            logger.info("Terminate the chat.")
            break
        inputs = {input_name: input_value, "chat_history": chat_history}
        with _get_input(executable_flow, input_path=input_path, additional_input=inputs) as input_file:
            # TODO remove this func and record run log
            disable_streaming_handler()

            with add_prefix():
                result = flow.run(input=input_file, connections=connections, run_id=run_id, log_path=log_path)
            if verbose:
                for node_result in result.detail["node_runs"]:
                    print(f"{Fore.CYAN}{node_result['node']}: ", end="")
                    print(f"{Fore.LIGHTWHITE_EX}{node_result['output']}")

            print(f"{Fore.YELLOW}Bot: ", end="")
            print(result.output[output_name][0])
            history = {"inputs": {input_name: input_value}, "outputs": {output_name: result.output[output_name][0]}}
            chat_history.append(history)
            _dump_result(result, path=Path(flow.code) / ".promptflow", prefix="chat")


def _is_chat_flow(flow):
    chat_inputs = [item for item in flow.inputs.values() if item.is_chat_input]
    return len(chat_inputs) == 1 and "chat_history" in flow.inputs


def test_flow(args):
    from promptflow.core import OperationContext
    from promptflow.sdk._load_functions import load_flow
    from promptflow.sdk._utils import parse_variant
    from promptflow.utils.logger_utils import LogContext

    if args.input and not args.input.endswith(".jsonl"):
        raise ValueError("Only support jsonl file as input.")

    if args.variant:
        tuning_node, variant = parse_variant(args.variant)
    else:
        tuning_node, variant = None, None
    flow = load_flow(source=args.flow)
    executable_flow = flow._init_executable(tuning_node, variant)
    connections = _get_connections_in_flow(executable_flow)

    with _get_input(executable_flow, node_name=args.node, input_path=args.input) as flow_input:
        if not args.interactive and args.debug:
            if not args.node:
                raise RuntimeError("Node is not defined, only support debugging a specific node in flow.")
            flow._single_node_debug(node_name=args.node, connections=connections, input=flow_input)
        else:
            (Path(flow.code) / ".promptflow").mkdir(exist_ok=True, parents=True)
            if "USER_AGENT" in os.environ:
                OperationContext.get_instance().user_agent = os.environ["USER_AGENT"]
                logger.info(f"Update the user agent to {OperationContext.get_instance().get_user_agent()}")
            if args.node:
                result = flow._single_node_run(node=args.node, input=flow_input, connections=connections)
                print(result.detail["node_runs"][0]["output"])
                _dump_result(result, path=Path(args.flow) / ".promptflow", prefix=f"flow-{args.node}.node")
            else:
                if args.interactive:
                    if not _is_chat_flow(executable_flow):
                        raise RuntimeError("Interactive only support chat flow.")

                    # TODO add description to comment
                    info_msg = f"Welcome to chat flow, {executable_flow.name}."
                    print("=" * len(info_msg))
                    print(info_msg)
                    print("Press Enter to send your message.")
                    print("You can quit with ctrl+Z.")
                    print("=" * len(info_msg))
                    _chat_flow(flow, executable_flow, connections, args.input, args.verbose)
                else:
                    log_path = Path(args.flow) / ".promptflow" / "flow.log"
                    run_id = datetime.now().strftime("run_%Y%m%d%H%M%S")
                    with LogContext(log_path, input_logger=logger):
                        result = flow.run(input=flow_input, connections=connections, run_id=run_id, log_path=log_path)
                    print(json.dumps(result.output, indent=2))
                    prefix = "flow"
                    if tuning_node and variant:
                        prefix = f"flow-{tuning_node}-{variant}"
                    _dump_result(result, path=Path(args.flow) / ".promptflow", prefix=prefix)


def serve_flow(args):
    logger.info("Start serve model: %s", args.source)
    # Set environment variable for local test
    source = Path(args.source)
    os.environ["PROMPTFLOW_PROJECT_PATH"] = source.absolute().as_posix()
    from promptflow.sdk._serving.app import create_app

    static_folder = args.static_folder or source
    static_folder = Path(static_folder).absolute().as_posix()
    logger.info(
        "Start prt server with port %s, static_folder: %s",
        args.port,
        static_folder,
    )
    # Change working directory to model dir
    print(f"Change working directory to model dir {source}")
    os.chdir(source)
    app = create_app(
        static_folder=static_folder, environment_variables=list_of_dict_to_dict(args.environment_variables)
    )
    # Debug is not supported for now as debug will rerun command, and we changed working directory.
    app.run(port=args.port, host=args.host)
    logger.info("Prt app ended")


def export_flow(args):
    from promptflow.sdk._load_functions import load_flow
    from promptflow.sdk.entities._flow import FlowProtected

    flow = load_flow(source=args.source)
    flow.__class__ = FlowProtected
    flow.export(
        output=args.output,
        format=args.format,
        migration_secret=get_migration_secret_from_args(args),
    )
    print(f"Exported flow to {args.output}, please check README.md under the folder for how to use it.")
