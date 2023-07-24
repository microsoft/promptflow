# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------


import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import List

from promptflow._constants import PROMPTFLOW_CONNECTIONS
from promptflow.core.connection_manager import ConnectionManager
from promptflow.runtime.score_client import _score
from promptflow.runtime.utils._utils import encode_dict

from ..client import _execute
from ..constants import PROMPTFLOW_ENCODED_CONNECTIONS, PROMPTFLOW_PROJECT_PATH, PRT_CONFIG_FILE
from ..runtime import PromptFlowRuntime
from ..runtime_config import RuntimeConfig, load_runtime_config
from ..utils import FORMATTER, get_logger
from .upgrade import upgrade

logger = get_logger("prt", std_out=True, log_formatter=FORMATTER)


class AppendToDictAction(argparse._AppendAction):  # pylint: disable=protected-access
    def __call__(self, parser, namespace, values, option_string=None):
        action = self.get_action(values, option_string)
        super(AppendToDictAction, self).__call__(parser, namespace, action, option_string)

    def get_action(self, values, option_string):  # pylint: disable=no-self-use
        kwargs = {}
        for item in values:
            try:
                key, value = item.split("=", 1)
                kwargs[key] = value
            except ValueError:
                raise Exception("usage error: {} KEY=VALUE [KEY=VALUE ...]".format(option_string))
        return kwargs


def _entry(argv):
    """
    CLI tools for promptflow-runtime.
    """
    parser = argparse.ArgumentParser(
        prog="prt",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="PromptFlow Runtime CLI. [Preview]",
    )

    subparsers = parser.add_subparsers()

    add_parser_execute(subparsers)
    add_parser_start(subparsers)
    add_parser_upgrade(subparsers)
    add_parser_serve(subparsers)
    add_parser_score(subparsers)

    args, additional_args = parser.parse_known_args(argv)

    if args.action == "start":
        _start(runtime_config=args.config, additional_args=additional_args)

    elif args.action == "execute":
        _execute(
            input_file=args.file,
            key=args.key,
            url=args.url,
            connection_file=args.connection_config,
            config_file=args.config,
            submit_flow_request_file=args.submit_config,
            workspace_token=args.workspace_token,
        )
    elif args.action == "upgrade":
        upgrade(version=args.version, extra_index_url=args.extra_index_url)
    elif args.action == "serve":
        _serve(
            model=args.model,
            connection_file=args.connection_config,
            clear_connection=args.clear_connection_file,
            additional_args=additional_args,
        )
    elif args.action == "score":
        _score(inputs=args.inputs, input_file=args.input_file, url=args.url)


def _serve(model=None, connection_file=None, clear_connection=False, additional_args: List[str] = None):
    logger.info("Start serve model: %s additional args: %s", model, additional_args)
    config = load_runtime_config(file=None, args=additional_args)
    # Set environment variable for local test
    if model:
        os.environ[PROMPTFLOW_PROJECT_PATH] = Path(model).absolute().as_posix()
    if connection_file:
        os.environ[PROMPTFLOW_ENCODED_CONNECTIONS] = encode_connections(connection_file)
    # init the runtime
    PromptFlowRuntime.init(config)
    from promptflow.runtime.serving.app import create_app

    logger.info("Start prt server with port %s, static_folder: %s", config.app.port, config.app.static_folder)
    app = create_app(static_folder=config.app.static_folder)
    if clear_connection and connection_file:
        logger.info(f"Clear the connection file .. {connection_file}")
        try:
            os.remove(connection_file)
        except Exception as e:
            logger.warning(f"Connection file removed failed due to {e!r}. Please delete it manually.")
    # Change working directory to model dir
    os.chdir(model)
    # Debug is not supported for now as debug will rerun command, and we changed working directory.
    app.run(port=config.app.port, host=config.app.host)
    logger.info("Prt app ended")


def encode_connections(connection_file: str) -> str:
    if connection_file:
        # Set the env var for local test
        os.environ[PROMPTFLOW_CONNECTIONS] = Path(connection_file).absolute().as_posix()

    connection_manager = ConnectionManager()

    return encode_dict(connection_manager.to_connections_dict())


def _start(runtime_config=None, additional_args=None):
    """Start a prt server."""

    logger.info("Init runtime with config file: %s", runtime_config)
    config = load_runtime_config(runtime_config, additional_args)
    app_type = config.app.type
    if app_type == "dev":
        _start_dev_app(config)
    elif app_type == "command":
        _start_command_app(config)
    else:
        raise ValueError(f"Unknown app type: {app_type}")


def _start_dev_app(cfg: RuntimeConfig):
    # init the runtime
    base_dir = cfg.base_dir
    logger.info("Change working dir to: %s", base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    os.chdir(base_dir)

    PromptFlowRuntime.init(cfg)
    from promptflow.runtime.app import app

    logger.info("Start prt server with host %s, port %s", cfg.app.host, cfg.app.port)
    app.run(host=cfg.app.host, port=cfg.app.port, debug=cfg.app.debug)
    logger.info("Prt app ended")


def _start_command_app(cfg: RuntimeConfig):
    # write the runtime config, so app can create with correct behavior
    base_dir = cfg.base_dir
    base_dir.mkdir(parents=True, exist_ok=True)
    with open(base_dir / PRT_CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write(cfg.to_yaml())
    cmd = cfg.app.args
    logger.info("Start prt server with command %s, working_dir: %s", cmd, base_dir)
    # run wait for completion
    # subprocess.run(cmd, shell=True, check=True, cwd=base_dir)

    # run command without waiting
    subprocess.Popen(cmd, shell=True, stdin=None, stdout=None, stderr=None, close_fds=True, cwd=base_dir)
    logger.info("Prt server started")


def add_parser_start(subparsers):
    """The parser definition of prt start"""

    epilog_start = """
    Examples:

    # start a prt server with port 8080
    prt start app.port=8080

    # start a prt server with config file mir.yaml
    prt start --config mir.yaml app.port=8080

    """
    start_parser = subparsers.add_parser(
        "start",
        description="A CLI tool to start prt server.",
        epilog=epilog_start,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    start_parser.add_argument("--config", type=str, help="config file of the promptflow runtime.")
    start_parser.set_defaults(action="start")


def add_parser_execute(subparsers):
    """The parser definition of prt execute"""

    epilog_execute = """
    Examples:

    # Execute a flow with local runtime:
    prt execute --file ./flow.json --url http://localhost:8080 --connections service/data/secrets.json
    prt execute --file ./flow.json --url https://x.inference.ml.azure.com --key <your_key> --connections secrets.json

    """

    execute_parser = subparsers.add_parser(
        "execute",
        description="A CLI tool to execute promptflow by sending request to runtime endpoint.",
        epilog=epilog_execute,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    execute_parser.add_argument("--file", type=str, help="the flow request to execute.")
    execute_parser.add_argument("--url", type=str, help="url of a started server.")
    execute_parser.add_argument("--key", type=str, help="key to access the server.")
    execute_parser.add_argument("--connection_config", type=str, help="replace the connections api-key to real value.")
    execute_parser.add_argument("--config", type=str, help="config file", required=False)
    execute_parser.add_argument("--workspace_token", type=str, help="use workspace_token.", default=None)
    execute_parser.add_argument(
        "--submit_config", type=str, help="additional file contains fields to construct final SubmitFlowRequest."
    )
    execute_parser.set_defaults(action="execute")


def add_parser_serve(subparsers):
    """The parser definition of prt execute"""

    epilog_execute = """
    Examples:

    # Execute a flow with local runtime:
    prt serve --model ./flow_project --connections service/data/connections.json

    """
    serve_parser = subparsers.add_parser(
        "serve",
        description="A CLI tool to serve promptflow as a runtime endpoint.",
        epilog=epilog_execute,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    serve_parser.add_argument("--model", type=str, help="the flow model directory to serve.")
    serve_parser.add_argument("--connection_config", type=str, help="replace the connections api-key to real value.")
    serve_parser.add_argument(
        "--clear-connection-file", action="store_true", help="Clear connection file after serving endpoint start."
    )
    serve_parser.set_defaults(action="serve")


def add_parser_score(subparsers):
    """The parser definition of prt score"""

    epilog_execute = """
    Examples:

    # Execute a flow with local runtime:
    prt score --inputs question="When did OpenAI announced their chatgpt api?" --url http://localhost:8080
    prt score --input_file ./score_input.json --url http://localhost:8080

    """
    score_parser = subparsers.add_parser(
        "score",
        description="A CLI tool to score the severing runtime endpoint.",
        epilog=epilog_execute,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    score_parser.add_argument(
        "--inputs",
        help="the inputs of request to serving flow endpoint.",
        action=AppendToDictAction,
        nargs="+",
    )
    score_parser.add_argument("--input_file", type=str, help="the input file of request to serving flow endpoint.")
    score_parser.add_argument("--url", type=str, help="url of the serving endpoint.")
    score_parser.set_defaults(action="score")


def add_parser_upgrade(subparsers):
    """The parser definition of prt upgrade"""

    epilog_upgrade = """
    Examples:

    # upgrade promptflow sdk to specific version:
    prt upgrade --version 0.0.89855504

    """

    execute_parser = subparsers.add_parser(
        "upgrade",
        description="A CLI tool to upgrade promptflow runtime version in current environment. (WIP)",
        epilog=epilog_upgrade,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    execute_parser.add_argument("--version", type=str, help="the promptflow sdk version to upgrade.")
    execute_parser.add_argument("--extra_index_url", type=str, help="extra index url.", default=None)
    execute_parser.set_defaults(action="upgrade")


def main():
    """Entrance of prt CLI."""
    command_args = sys.argv[1:]
    if len(command_args) == 0:
        command_args.append("-h")
    _entry(command_args)


if __name__ == "__main__":
    main()
