import argparse
import json

from promptflow._cli._params import add_param_path, add_param_set_positional, base_params
from promptflow._cli._utils import activate_action, list_of_dict_to_dict
from promptflow._sdk._configuration import Configuration, InvalidConfigValue
from promptflow._sdk._utilities.general_utils import print_red_error
from promptflow._utils.logger_utils import get_cli_sdk_logger

logger = get_cli_sdk_logger()


def add_config_set(subparsers):
    epilog = """
    Examples:

    # Config connection provider to azure workspace for current user:
    pf config set connection.provider="azureml://subscriptions/<your-subscription>/resourceGroups/<your-resourcegroup>/providers/Microsoft.MachineLearningServices/workspaces/<your-workspace>"
    """  # noqa: E501
    activate_action(
        name="set",
        description="Set prompt flow configs for current user.",
        epilog=epilog,
        add_params=[add_param_set_positional, add_param_path] + base_params,
        subparsers=subparsers,
        help_message="Set prompt flow configs for current user, configs will be stored at ~/.promptflow/pf.yaml.",
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
        add_params=base_params,
        subparsers=subparsers,
        help_message="Show prompt flow configs for current user.",
        action_param_name="sub_action",
    )


def add_config_parser(subparsers):
    config_parser = subparsers.add_parser(
        "config", description="A CLI tool to set prompt flow configs for current user.", help="Manage configs."
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
    path = args.path
    for k, v in params_override.items():
        logger.debug("Setting config %s to %s", k, v)
        try:
            new_temp_path = path if isinstance(path, str) else Configuration.CONFIG_PATH.parent
            with Configuration.set_temp_config_path(new_temp_path):
                Configuration.get_instance().set_config(k, v)
                print(f"Set config {args.params_override} successfully.")
        except InvalidConfigValue as e:
            error_message = f"Invalid config value {v!r} for {k!r}: {str(e)}"
            print_red_error(error_message)


def show_config():
    configs = Configuration.get_instance().get_all()
    print(json.dumps(configs, indent=4))
