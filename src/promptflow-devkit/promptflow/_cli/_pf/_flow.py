# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse
import importlib
import json
import os
import sys
import tempfile
from pathlib import Path

from promptflow._cli._params import (
    AppendToDictAction,
    add_param_config,
    add_param_entry,
    add_param_environment_variables,
    add_param_flow_display_name,
    add_param_function,
    add_param_init,
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
from promptflow._cli._utils import _copy_to_flow, activate_action, confirm, inject_sys_path, list_of_dict_to_dict
from promptflow._constants import ConnectionProviderConfig
from promptflow._sdk._configuration import Configuration
from promptflow._sdk._constants import DEFAULT_SERVE_ENGINE, PROMPT_FLOW_DIR_NAME
from promptflow._sdk._pf_client import PFClient
from promptflow._sdk._utilities.chat_utils import start_chat_ui_service_monitor
from promptflow._sdk._utilities.serve_utils import find_available_port, start_flow_service
from promptflow._utils.flow_utils import is_flex_flow
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow.exceptions import ErrorTarget, UserErrorException

DEFAULT_CONNECTION = "open_ai_connection"
DEFAULT_DEPLOYMENT = "gpt-35-turbo"
PF_CHAT_UI_ENABLE_STREAMLIT = "pf_chat_ui_enable_streamlit"
logger = get_cli_sdk_logger()


def add_flow_parser(subparsers):
    """Add flow parser to the pf subparsers."""
    flow_parser = subparsers.add_parser(
        "flow",
        description="Manage flows for promptflow.",
        help="Manage flows.",
    )
    flow_subparsers = flow_parser.add_subparsers()
    add_parser_init_flow(flow_subparsers)
    add_parser_save_flow(flow_subparsers)
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
    elif args.sub_action == "save":
        save_flow(args)


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


def add_parser_save_flow(subparsers):
    """Add flow save parser to the pf flow subparsers."""
    epilog = """
Examples:

# Creating a flex flow folder in a specific path.
# There should be a src/intent.py file with extract_intent function defined.
# After running this command, all content in the src folder will be copied to my-awesome-flow folder;
# and a flow.flex.yaml will be created in my-awesome-flow folder.
pf flow save --path my-awesome-flow --entry intent:extract_intent --code src
# Creating a flow.flex.yaml under current folder with intent:extract_intent as entry.
pf flow save --entry intent:extract_intent
"""  # noqa: E501
    add_params = [
        lambda parser: parser.add_argument(
            "--entry",
            type=str,
            help="The entry to be saved as a flex flow, should be relative to code.",
            required=True,
        ),
        lambda parser: parser.add_argument(
            "--code",
            type=str,
            help="The folder or file containing the snapshot for the flex flow. Default to current folder.",
        ),
        lambda parser: parser.add_argument(
            "--path",
            type=str,
            help="The path to save the flow. Will create flow.flex.yaml under code if not specified.",
        ),
    ] + base_params
    activate_action(
        name="save",
        description="Creating a flex flow with a specific callable class or a specific function as entry.",
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Save a callable class or a function as a flex flow.",
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
    add_param_engine = lambda parser: parser.add_argument(  # noqa: E731
        "--engine",
        type=str,
        default=DEFAULT_SERVE_ENGINE,
        help="The engine to serve the flow, can be flask or fastapi.",
    )
    activate_action(
        name="serve",
        description="Serving a flow as an endpoint.",
        epilog=epilog,
        add_params=[
            add_param_source,
            add_param_port,
            add_param_host,
            add_param_engine,
            add_param_static_folder,
            add_param_environment_variables,
            add_param_config,
            add_param_skip_browser,
            add_param_init,
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
# Test a flow with init kwargs:
pf flow test --flow my-awesome-flow --init key1=value1 key2=value2
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
    add_param_ui = lambda parser: parser.add_argument(  # noqa: E731
        "--ui", action="store_true", help="The flag to start an interactive chat experience in local chat window."
    )
    add_param_input = lambda parser: parser.add_argument("--input", type=str, help=argparse.SUPPRESS)  # noqa: E731
    add_param_detail = lambda parser: parser.add_argument(  # noqa: E731
        "--detail", type=str, default=None, required=False, help=argparse.SUPPRESS
    )
    add_param_experiment = lambda parser: parser.add_argument(  # noqa: E731
        "--experiment", type=str, help="the experiment template path of flow."
    )
    add_param_collection = lambda parser: parser.add_argument(  # noqa: E731
        "--collection", type=str, help="the collection of flow test trace."
    )
    add_param_skip_browser = lambda parser: parser.add_argument(  # noqa: E731
        "--skip-open-browser", action="store_true", help=argparse.SUPPRESS
    )
    add_param_url_params = lambda parser: parser.add_argument(  # noqa: E731
        "--url-params", action=AppendToDictAction, help=argparse.SUPPRESS, nargs="+"
    )
    # add a private param to support specifying port for chat debug service
    add_param_port = lambda parser: parser.add_argument("--port", type=str, help=argparse.SUPPRESS)  # noqa: E731

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
        add_param_collection,
        add_param_skip_browser,
        add_param_init,
        add_param_url_params,
        add_param_port,
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
    is_local_connection = Configuration.get_instance().get_connection_provider() == ConnectionProviderConfig.LOCAL
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
        _test_flow_multi_modal(args, pf_client, environment_variables)
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


def _test_flow_multi_modal(args, pf_client, environment_variables):
    """Test flow with multi modality mode."""
    if str(os.getenv(PF_CHAT_UI_ENABLE_STREAMLIT, "false")).lower() == "true":
        from promptflow._sdk._load_functions import load_flow

        if is_flex_flow(flow_path=args.flow):
            error = ValueError("Only support dag yaml in streamlit ui.")
            raise UserErrorException(
                target=ErrorTarget.CONTROL_PLANE_SDK,
                message=str(error),
                error=error,
            )
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
                    flow_dag_path=flow._flow_file_path,
                ).generate_to_file(script)
            main_script_path = os.path.join(temp_dir, "main.py")
            logger.info("Start streamlit with main script generated at: %s", main_script_path)
            pf_client.flows._chat_with_ui(script=main_script_path, skip_open_browser=args.skip_open_browser)
    else:
        from promptflow._sdk._tracing import _invoke_pf_svc

        pfs_port, service_host = _invoke_pf_svc()
        serve_app_port = args.port or find_available_port()
        enable_internal_features = Configuration.get_instance().is_internal_features_enabled()
        start_chat_ui_service_monitor(
            flow=args.flow,
            serve_app_port=serve_app_port,
            pfs_port=pfs_port,
            service_host=service_host,
            url_params=list_of_dict_to_dict(args.url_params),
            init=list_of_dict_to_dict(args.init),
            enable_internal_features=enable_internal_features,
            skip_open_browser=args.skip_open_browser,
            environment_variables=environment_variables,
        )


def _test_flow_interactive(args, pf_client, inputs, environment_variables):
    """Test flow with interactive mode."""
    pf_client.flows._chat(
        flow=args.flow,
        inputs=inputs,
        environment_variables=environment_variables,
        variant=args.variant,
        show_step_output=args.verbose,
        collection=args.collection,
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
        init=list_of_dict_to_dict(args.init),
        collection=args.collection,
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
        collection=args.collection,
    )
    print(json.dumps(node_results, indent=4, ensure_ascii=False))


def serve_flow(args):
    logger.info("Start serve model: %s", args.source)
    # Set environment variable for local test
    start_flow_service(
        source=Path(args.source),
        static_folder=args.static_folder,
        config=list_of_dict_to_dict(args.config),
        environment_variables=list_of_dict_to_dict(args.environment_variables),
        init=list_of_dict_to_dict(args.init),
        host=args.host,
        port=args.port,
        skip_open_browser=args.skip_open_browser,
        engine=args.engine,
    )
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
        sys.exit(1)
    else:
        sys.exit(0)


def save_flow(args):
    pf_client = PFClient()

    pf_client.flows.save(
        entry=args.entry,
        code=args.code or os.curdir,
        path=args.path,
    )
    print(f"Saved flow to {Path(args.path or args.code or os.curdir).absolute().as_posix()}.")
