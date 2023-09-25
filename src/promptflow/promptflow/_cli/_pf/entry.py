# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import argparse
import logging
import sys
import timeit

from promptflow._cli._pf._config import add_config_parser, dispatch_config_commands
from promptflow._cli._pf._connection import add_connection_parser, dispatch_connection_commands
from promptflow._cli._pf._flow import add_flow_parser, dispatch_flow_commands
from promptflow._cli._pf._run import add_run_parser, dispatch_run_commands
from promptflow._cli._user_agent import USER_AGENT
from promptflow._sdk._constants import LOGGER_NAME
from promptflow._sdk._logger_factory import LoggerFactory
from promptflow._sdk._utils import get_promptflow_sdk_version, setup_user_agent_to_operation_context

# Log the start time
start_time = timeit.default_timer()

# configure logger for CLI
logger = LoggerFactory.get_logger(name=LOGGER_NAME, verbosity=logging.WARNING)


def entry(argv):
    """
    Control plane CLI tools for promptflow.
    """
    parser = argparse.ArgumentParser(
        prog="pf",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="PromptFlow CLI. [Preview]",
    )
    parser.add_argument(
        "-v", "--version", dest="version", action="store_true", help="show current CLI version and exit"
    )

    subparsers = parser.add_subparsers()
    add_flow_parser(subparsers)
    add_connection_parser(subparsers)
    add_run_parser(subparsers)
    add_config_parser(subparsers)

    args = parser.parse_args(argv)
    # Log the init finish time
    init_finish_time = timeit.default_timer()
    try:
        # --verbose, enable info logging
        if hasattr(args, "verbose") and args.verbose:
            for handler in logging.getLogger(LOGGER_NAME).handlers:
                handler.setLevel(logging.INFO)
        # --debug, enable debug logging
        if hasattr(args, "debug") and args.debug:
            for handler in logging.getLogger(LOGGER_NAME).handlers:
                handler.setLevel(logging.DEBUG)
        if args.version:
            print(get_promptflow_sdk_version())
        elif args.action == "flow":
            dispatch_flow_commands(args)
        elif args.action == "connection":
            dispatch_connection_commands(args)
        elif args.action == "run":
            dispatch_run_commands(args)
        elif args.action == "config":
            dispatch_config_commands(args)
    except KeyboardInterrupt as ex:
        logger.debug("Keyboard interrupt is captured.")
        raise ex
    except SystemExit as ex:  # some code directly call sys.exit, this is to make sure command metadata is logged
        exit_code = ex.code if ex.code is not None else 1
        logger.debug(f"Code directly call sys.exit with code {exit_code}")
        raise ex
    except Exception as ex:
        logger.debug(f"Command {args} execute failed. {str(ex)}")
        raise ex
    finally:
        # Log the invoke finish time
        invoke_finish_time = timeit.default_timer()
        logger.info(
            "Command ran in %.3f seconds (init: %.3f, invoke: %.3f)",
            invoke_finish_time - start_time,
            init_finish_time - start_time,
            invoke_finish_time - init_finish_time,
        )


def main():
    """Entrance of pf CLI."""
    command_args = sys.argv[1:]
    if len(command_args) == 0:
        command_args.append("-h")
    setup_user_agent_to_operation_context(USER_AGENT)
    entry(command_args)


if __name__ == "__main__":
    main()
