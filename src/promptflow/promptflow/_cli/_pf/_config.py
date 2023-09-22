import argparse
import json
import logging

from promptflow._cli._params import add_param_set_positional, logging_params
from promptflow._cli._utils import activate_action, list_of_dict_to_dict
from promptflow._sdk._configuration import Configuration
from promptflow._sdk._constants import LOGGER_NAME

logger = logging.getLogger(LOGGER_NAME)


def add_config_set(subparsers):
    epilog = """
    Examples:

    # Config connection provider to azure workspace for current user:
    pf config set connection.provider="azureml:/subscriptions/<your-subscription>/resourceGroups/<your-resourcegroup>/providers/Microsoft.MachineLearningServices/workspaces/<your-workspace>"
    """  # noqa: E501
    activate_action(
        name="set",
        description="Set promptflow configs for current user.",
        epilog=epilog,
        add_params=[add_param_set_positional] + logging_params,
        subparsers=subparsers,
        help_message="Set promptflow configs for current user.",
        action_param_name="sub_action",
    )


def add_config_show(subparsers):
    epilog = """
    Examples:

    # Show prompt flow for current user:
    pf config show
    """
    activate_action(
        name="show",
        description="Show prompt flow configs for current user.",
        epilog=epilog,
        add_params=logging_params,
        subparsers=subparsers,
        help_message="Show prompt flow configs for current user.",
        action_param_name="sub_action",
    )


def add_config_parser(subparsers):
    config_parser = subparsers.add_parser(
        "config", description="A CLI tool to set promptflow configs for current user.", help="pf config"
    )
    subparsers = config_parser.add_subparsers()
    add_config_set(subparsers)
    add_config_show(subparsers)
    config_parser.set_defaults(action="config")


def dispatch_config_commands(args: argparse.Namespace):
    if args.sub_action == "set":
        set_config(args)
    if args.sub_action == "show":
        show_config()


def set_config(args):
    params_override = list_of_dict_to_dict(args.params_override)
    for k, v in params_override.items():
        logger.debug("Setting config %s to %s", k, v)
        Configuration.get_instance().set_config(k, v)
    print(f"Set config {args.params_override} successfully.")


def show_config():
    configs = Configuration.get_instance().get_all()
    print(json.dumps(configs, indent=4))
