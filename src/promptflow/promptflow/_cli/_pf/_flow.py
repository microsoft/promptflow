# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import webbrowser
from pathlib import Path

from promptflow._cli._params import (
    add_param_config,
    add_param_entry,
    add_param_environment_variables,
    add_param_flow_display_name,
    add_param_function,
    add_param_inputs,
    add_param_prompt_template,
    add_param_source,
    add_param_yes,
    add_parser_build,
    base_params,
)
from promptflow._cli._pf._init_entry_generators import (
    AzureOpenAIConnectionGenerator,
    ChatFlowDAGGenerator,
    FlowDAGGenerator,
    OpenAIConnectionGenerator,
    StreamlitFileReplicator,
    ToolMetaGenerator,
    ToolPyGenerator,
    copy_extra_files,
)
from promptflow._cli._pf._run import exception_handler
from promptflow._cli._utils import _copy_to_flow, activate_action, confirm, inject_sys_path, list_of_dict_to_dict
from promptflow._constants import FlowLanguage
from promptflow._sdk._configuration import Configuration
from promptflow._sdk._constants import PROMPT_FLOW_DIR_NAME, ConnectionProvider
from promptflow._sdk._pf_client import PFClient
from promptflow._sdk.operations._flow_operations import FlowOperations
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow.exceptions import ErrorTarget, UserErrorException

DEFAULT_CONNECTION = "open_ai_connection"
DEFAULT_DEPLOYMENT = "gpt-35-turbo"
logger = get_cli_sdk_logger()


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
    add_param_connection = lambda parser: parser.add_argument(  # noqa: E731
        "--connection", type=str, help=argparse.SUPPRESS
    )
    add_param_deployment = lambda parser: parser.add_argument(  # noqa: E731
        "--deployment", type=str, help=argparse.SUPPRESS
    )

    add_params = [
        add_param_type,
        add_param_yes,
        add_param_flow_display_name,
        add_param_entry,
        add_param_function,
        add_param_prompt_template,
        add_param_connection,
        add_param_deployment,
    ] + base_params
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
# Serve flow without opening browser:
pf flow serve --source <path_to_flow> --skip-open-browser
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
    add_param_skip_browser = lambda parser: parser.add_argument(  # noqa: E731
        "--skip-open-browser", action="store_true", default=False, help="Skip open browser for flow serving."
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
            add_param_config,
            add_param_skip_browser,
        ]
        + base_params,
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
        ]
        + base_params,
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
    add_param_multi_modal = lambda parser: parser.add_argument(  # noqa: E731
        "--multi-modal", action="store_true", help=argparse.SUPPRESS
    )
    add_param_ui = lambda parser: parser.add_argument("--ui", action="store_true", help=argparse.SUPPRESS)  # noqa: E731
    add_param_input = lambda parser: parser.add_argument("--input", type=str, help=argparse.SUPPRESS)  # noqa: E731
    add_param_detail = lambda parser: parser.add_argument(  # noqa: E731
        "--detail", type=str, default=None, required=False, help=argparse.SUPPRESS
    )
    add_param_experiment = lambda parser: parser.add_argument(  # noqa: E731
        "--experiment", type=str, help="the experiment template path of flow."
    )

    add_params = [
        add_param_flow,
        add_param_node,
        add_param_variant,
        add_param_interactive,
        add_param_input,
        add_param_inputs,
        add_param_environment_variables,
        add_param_multi_modal,
        add_param_ui,
        add_param_config,
        add_param_detail,
    ] + base_params

    if Configuration.get_instance().is_internal_features_enabled():
        add_params.append(add_param_experiment)
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
        _init_flow_by_template(args.flow, args.type, args.yes, args.connection, args.deployment)


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
            error = ValueError(f"Template parameter {tool_input} doesn't find in python function arguments.")
            raise UserErrorException(target=ErrorTarget.CONTROL_PLANE_SDK, message=str(error), error=error)

    python_tool.generate_to_file(tool_py)
    # Create .promptflow and flow.tools.json
    meta_dir = flow_path / PROMPT_FLOW_DIR_NAME
    meta_dir.mkdir(parents=True, exist_ok=True)
    tools.generate_to_file(meta_dir / "flow.tools.json")
    # Create flow.dag.yaml
    FlowDAGGenerator(tool_py, function, function_obj, prompt_params).generate_to_file("flow.dag.yaml")
    copy_extra_files(flow_path=flow_path, extra_files=["requirements.txt", ".gitignore"])
    print(f"Done. Generated flow in folder: {flow_path.resolve()}.")


def _init_chat_flow(flow_name, flow_path, connection=None, deployment=None):
    from promptflow._sdk._configuration import Configuration

    example_flow_path = Path(__file__).parent.parent / "data" / "chat_flow" / "flow_files"
    for item in list(example_flow_path.iterdir()):
        _copy_to_flow(flow_path=flow_path, source_file=item)

    # Generate flow.dag.yaml to chat flow.
    connection = connection or DEFAULT_CONNECTION
    deployment = deployment or DEFAULT_DEPLOYMENT
    ChatFlowDAGGenerator(connection=connection, deployment=deployment).generate_to_file(flow_path / "flow.dag.yaml")
    # When customer not configure the remote connection provider, create connection yaml to chat flow.
    is_local_connection = Configuration.get_instance().get_connection_provider() == ConnectionProvider.LOCAL
    if is_local_connection:
        OpenAIConnectionGenerator(connection=connection).generate_to_file(flow_path / "openai.yaml")
        AzureOpenAIConnectionGenerator(connection=connection).generate_to_file(flow_path / "azure_openai.yaml")

    copy_extra_files(flow_path=flow_path, extra_files=["requirements.txt", ".gitignore"])

    print(f"Done. Created chat flow folder: {flow_path.resolve()}.")
    if is_local_connection:
        print(
            f"The generated chat flow is requiring a connection named {connection}, "
            "please follow the steps in README.md to create if you haven't done that."
        )
    else:
        print(
            f"The generated chat flow is requiring a connection named {connection}, "
            "please ensure it exists in workspace."
        )
    flow_test_command = f"pf flow test --flow {flow_name} --interactive"
    print(f"You can execute this command to test the flow, {flow_test_command}")


def _init_standard_or_evaluation_flow(flow_name, flow_path, flow_type):
    example_flow_path = Path(__file__).parent.parent / "data" / f"{flow_type}_flow"
    for item in list(example_flow_path.iterdir()):
        _copy_to_flow(flow_path=flow_path, source_file=item)
    copy_extra_files(flow_path=flow_path, extra_files=["requirements.txt", ".gitignore"])
    print(f"Done. Created {flow_type} flow folder: {flow_path.resolve()}.")
    flow_test_command = f"pf flow test --flow {flow_name} --input {os.path.join(flow_name, 'data.jsonl')}"
    print(f"You can execute this command to test the flow, {flow_test_command}")


def _init_flow_by_template(flow_name, flow_type, overwrite=False, connection=None, deployment=None):
    flow_path = Path(flow_name)
    if flow_path.exists():
        if not flow_path.is_dir():
            logger.error(f"{flow_path.resolve()} is not a folder.")
            return
        answer = confirm(
            "The flow folder already exists, do you want to create the flow in this existing folder?", overwrite
        )
        if not answer:
            print("The 'pf init' command has been cancelled.")
            return
    flow_path.mkdir(parents=True, exist_ok=True)
    if flow_type == "chat":
        _init_chat_flow(flow_name=flow_name, flow_path=flow_path, connection=connection, deployment=deployment)
    else:
        _init_standard_or_evaluation_flow(flow_name=flow_name, flow_path=flow_path, flow_type=flow_type)


@exception_handler("Flow test")
def test_flow(args):
    config = list_of_dict_to_dict(args.config)
    pf_client = PFClient(config=config)

    if args.environment_variables:
        environment_variables = list_of_dict_to_dict(args.environment_variables)
    else:
        environment_variables = {}
    inputs = _build_inputs_for_flow_test(args)
    # Select different test mode
    if Configuration.get_instance().is_internal_features_enabled() and args.experiment:
        _test_flow_experiment(args, pf_client, inputs, environment_variables)
        return
    if args.multi_modal or args.ui:
        _test_flow_multi_modal(args, pf_client)
        return
    if args.interactive:
        _test_flow_interactive(args, pf_client, inputs, environment_variables)
        return
    _test_flow_standard(args, pf_client, inputs, environment_variables)


def _build_inputs_for_flow_test(args):
    """Build inputs from --input and --inputs for flow test."""
    inputs = {}
    if args.input:
        from promptflow._utils.load_data import load_data

        if args.input and not args.input.endswith(".jsonl"):
            error = ValueError("Only support jsonl file as input.")
            raise UserErrorException(
                target=ErrorTarget.CONTROL_PLANE_SDK,
                message=str(error),
                error=error,
            )
        inputs = load_data(local_path=args.input)[0]
    if args.inputs:
        inputs.update(list_of_dict_to_dict(args.inputs))
    return inputs


def _test_flow_multi_modal(args, pf_client):
    """Test flow with multi modality mode."""
    from promptflow._sdk._load_functions import load_flow

    with tempfile.TemporaryDirectory() as temp_dir:
        flow = load_flow(args.flow)

        script_path = [
            os.path.join(temp_dir, "main.py"),
            os.path.join(temp_dir, "utils.py"),
            os.path.join(temp_dir, "logo.png"),
        ]
        for script in script_path:
            StreamlitFileReplicator(
                flow_name=flow.display_name if flow.display_name else flow.name,
                flow_dag_path=flow.flow_dag_path,
            ).generate_to_file(script)
        main_script_path = os.path.join(temp_dir, "main.py")
        pf_client.flows._chat_with_ui(script=main_script_path)


def _test_flow_interactive(args, pf_client, inputs, environment_variables):
    """Test flow with interactive mode."""
    pf_client.flows._chat(
        flow=args.flow,
        inputs=inputs,
        environment_variables=environment_variables,
        variant=args.variant,
        show_step_output=args.verbose,
    )


def _test_flow_standard(args, pf_client, inputs, environment_variables):
    """Test flow with standard mode."""
    result = pf_client.flows.test(
        flow=args.flow,
        inputs=inputs,
        environment_variables=environment_variables,
        variant=args.variant,
        node=args.node,
        allow_generator_output=False,
        stream_output=False,
        dump_test_result=True,
        output_path=args.detail,
    )
    # Print flow/node test result
    if isinstance(result, dict):
        print(json.dumps(result, indent=4, ensure_ascii=False))
    else:
        print(result)


def _test_flow_experiment(args, pf_client, inputs, environment_variables):
    """Test flow with experiment specified."""
    if args.variant or args.node:
        error = ValueError("--variant or --node is not supported experiment is specified.")
        raise UserErrorException(
            target=ErrorTarget.CONTROL_PLANE_SDK,
            message=str(error),
            error=error,
        )
    node_results = pf_client.flows.test(
        flow=args.flow,
        inputs=inputs,
        environment_variables=environment_variables,
        experiment=args.experiment,
        output_path=args.detail,
    )
    print(json.dumps(node_results, indent=4, ensure_ascii=False))


def serve_flow(args):
    from promptflow._sdk._load_functions import load_flow

    logger.info("Start serve model: %s", args.source)
    # Set environment variable for local test
    source = Path(args.source)
    logger.info(
        "Start promptflow server with port %s",
        args.port,
    )
    os.environ["PROMPTFLOW_PROJECT_PATH"] = source.absolute().as_posix()
    flow = load_flow(args.source)
    if flow.language == FlowLanguage.CSharp:
        serve_flow_csharp(args, source)
    else:
        serve_flow_python(args, source)
    logger.info("Promptflow app ended")


def serve_flow_csharp(args, source):
    from promptflow.batch._csharp_executor_proxy import EXECUTOR_SERVICE_DLL

    try:
        # Change working directory to model dir
        logger.info(f"Change working directory to model dir {source}")
        os.chdir(source)
        command = [
            "dotnet",
            EXECUTOR_SERVICE_DLL,
            "--port",
            str(args.port),
            "--yaml_path",
            "flow.dag.yaml",
            "--assembly_folder",
            ".",
            "--connection_provider_url",
            "",
            "--log_path",
            "",
            "--serving",
        ]
        subprocess.run(command, stdout=sys.stdout, stderr=sys.stderr)
    except KeyboardInterrupt:
        pass


def _resolve_python_flow_additional_includes(source) -> Path:
    # Resolve flow additional includes
    from promptflow import load_flow

    flow = load_flow(source)
    with FlowOperations._resolve_additional_includes(flow.path) as resolved_flow_path:
        if resolved_flow_path == flow.path:
            return source
        # Copy resolved flow to temp folder if additional includes exists
        # Note: DO NOT use resolved flow path directly, as when inner logic raise exception,
        # temp dir will fail due to file occupied by other process.
        temp_flow_path = Path(tempfile.TemporaryDirectory().name)
        shutil.copytree(src=resolved_flow_path.parent, dst=temp_flow_path, dirs_exist_ok=True)

    return temp_flow_path


def serve_flow_python(args, source):
    from promptflow._sdk._serving.app import create_app

    static_folder = args.static_folder
    if static_folder:
        static_folder = Path(static_folder).absolute().as_posix()
    config = list_of_dict_to_dict(args.config)
    source = _resolve_python_flow_additional_includes(source)
    os.environ["PROMPTFLOW_PROJECT_PATH"] = source.absolute().as_posix()
    logger.info(f"Change working directory to model dir {source}")
    os.chdir(source)
    app = create_app(
        static_folder=static_folder,
        environment_variables=list_of_dict_to_dict(args.environment_variables),
        config=config,
    )
    if not args.skip_open_browser:
        target = f"http://{args.host}:{args.port}"
        logger.info(f"Opening browser {target}...")
        webbrowser.open(target)
    # Debug is not supported for now as debug will rerun command, and we changed working directory.
    app.run(port=args.port, host=args.host)


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
