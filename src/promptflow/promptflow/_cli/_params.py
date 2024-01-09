# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse

from promptflow._sdk._constants import PROMPT_FLOW_DIR_NAME, PROMPT_FLOW_RUNS_DIR_NAME, CLIListOutputFormat, FlowType

# TODO: avoid azure dependency here
MAX_LIST_CLI_RESULTS = 50


class AppendToDictAction(argparse._AppendAction):  # pylint: disable=protected-access
    def __call__(self, parser, namespace, values, option_string=None):
        action = self.get_action(values, option_string)
        super(AppendToDictAction, self).__call__(parser, namespace, action, option_string)

    def get_action(self, values, option_string):  # pylint: disable=no-self-use
        from promptflow._sdk._utils import strip_quotation

        kwargs = {}
        for item in values:
            try:
                key, value = strip_quotation(item).split("=", 1)
                kwargs[key] = strip_quotation(value)
            except ValueError:
                raise Exception("Usage error: {} KEY=VALUE [KEY=VALUE ...]".format(option_string))
        return kwargs


class FlowTestInputAction(AppendToDictAction):  # pylint: disable=protected-access
    def get_action(self, values, option_string):  # pylint: disable=no-self-use
        if len(values) == 1 and "=" not in values[0]:
            from promptflow._utils.load_data import load_data

            if not values[0].endswith(".jsonl"):
                raise ValueError("Only support jsonl file as input.")
            return load_data(local_path=values[0])[0]
        else:
            return super().get_action(values, option_string)


def add_param_yes(parser):
    parser.add_argument(
        "-y",
        "--yes",
        "--assume-yes",
        action="store_true",
        help="Automatic yes to all prompts; assume 'yes' as answer to all prompts and run non-interactively.",
    )


def add_param_ua(parser):
    # suppress user agent for now since it's only used in vscode extension
    parser.add_argument("--user-agent", help=argparse.SUPPRESS)


def add_param_flow_display_name(parser):
    parser.add_argument("--flow", type=str, required=True, help="The flow name to create.")


def add_param_entry(parser):
    parser.add_argument("--entry", type=str, help="The entry file.")


def add_param_function(parser):
    parser.add_argument("--function", type=str, help="The function name in entry file.")


def add_param_prompt_template(parser):
    parser.add_argument(
        "--prompt-template", action=AppendToDictAction, help="The prompt template parameter and assignment.", nargs="+"
    )


def add_param_set(parser):
    parser.add_argument(
        "--set",
        dest="params_override",
        action=AppendToDictAction,
        help="Update an object by specifying a property path and value to set. Example: --set "
        "property1.property2=<value>.",
        nargs="+",
    )


def add_param_set_positional(parser):
    parser.add_argument(
        "params_override",
        action=AppendToDictAction,
        help="Set an object by specifying a property path and value to set. Example: set "
        "property1.property2=<value>.",
        nargs="+",
    )


def add_param_environment_variables(parser):
    parser.add_argument(
        "--environment-variables",
        action=AppendToDictAction,
        help="Environment variables to set by specifying a property path and value. Example: --environment-variable "
        "key1='${my_connection.api_key}' key2='value2'. The value reference to connection keys will be resolved "
        "to the actual value, and all environment variables specified will be set into os.environ.",
        nargs="+",
    )


def add_param_connections(parser):
    parser.add_argument(
        "--connections",
        action=AppendToDictAction,
        help="Overwrite node level connections with provided value. Example: --connections "
        "node1.connection=test_llm_connection node1.deployment_name=gpt-35-turbo",
        nargs="+",
    )


def add_param_columns_mapping(parser):
    parser.add_argument(
        "--column-mapping",
        action=AppendToDictAction,
        help="Inputs column mapping, use ${data.xx} to refer to data columns, "
        "use ${run.inputs.xx} to refer to referenced run's data columns. "
        "and use ${run.outputs.xx} to refer to referenced run's output columns."
        "Example: --column-mapping data1='${data.data1}' data2='${run.inputs.data2}' data3='${run.outputs.data3}'",
        nargs="+",
    )


def add_param_set_tool_extra_info(parser):
    parser.add_argument(
        "--set",
        dest="extra_info",
        action=AppendToDictAction,
        help="Set extra information about the tool. Example: --set <key>=<value>.",
        nargs="+",
    )


def add_param_inputs(parser):
    parser.add_argument(
        "--inputs",
        action=FlowTestInputAction,
        help="Input datas of file for the flow. Example: --inputs data1=data1_val data2=data2_val",
        nargs="+",
    )


def add_param_env(parser):
    parser.add_argument(
        "--env",
        type=str,
        default=None,
        help="The dotenv file path containing the environment variables to be used in the flow.",
    )


def add_param_output(parser):
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        help=(
            f"The output directory to store the results. "
            f"Default to be ~/{PROMPT_FLOW_DIR_NAME}/{PROMPT_FLOW_RUNS_DIR_NAME} if not specified."
        ),
    )


def add_param_overwrite(parser):
    parser.add_argument("--overwrite", action="store_true", help="Overwrite the existing results.")


def add_param_source(parser):
    parser.add_argument("--source", type=str, required=True, help="The flow or run source to be used.")


def add_param_run_name(parser):
    parser.add_argument("-n", "--name", required=True, type=str, help="Name of the run.")


def add_param_connection_name(parser):
    parser.add_argument("-n", "--name", type=str, help="Name of the connection to create.")


def add_param_max_results(parser):
    parser.add_argument(  # noqa: E731
        "-r",
        "--max-results",
        dest="max_results",
        type=int,
        default=MAX_LIST_CLI_RESULTS,
        help=f"Max number of results to return. Default is {MAX_LIST_CLI_RESULTS}.",
    )


def add_param_all_results(parser):
    parser.add_argument(  # noqa: E731
        "--all-results",
        action="store_true",
        dest="all_results",
        default=False,
        help="Returns all results. Default to False.",
    )


def add_param_variant(parser):
    parser.add_argument(
        "--variant",
        "-v",
        type=str,
        help="The variant to be used in flow, will use default variant if not specified.",
    )


def add_parser_build(subparsers, entity_name: str):
    add_param_build_output = lambda parser: parser.add_argument(  # noqa: E731
        "--output", "-o", required=True, type=str, help="The destination folder path."
    )
    add_param_format = lambda parser: parser.add_argument(  # noqa: E731
        "--format", "-f", type=str, help="The format to build with.", choices=["docker", "executable"]
    )
    # this is a hidden parameter for `mldesigner compile` command
    add_param_flow_only = lambda parser: parser.add_argument(  # noqa: E731
        "--flow-only",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    add_params = [
        add_param_source,
        add_param_build_output,
        add_param_format,
        add_param_flow_only,
        add_param_variant,
    ] + base_params
    from promptflow._cli._utils import activate_action

    description = f"Build a {entity_name} for further sharing or deployment."

    activate_action(
        name="build",
        description=description,
        epilog=f"pf {entity_name} build --source <source> --output <output> --format " f"docker|package",
        add_params=add_params,
        subparsers=subparsers,
        action_param_name="sub_action",
        help_message=description,
    )


def add_param_debug(parser):
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="The flag to turn on debug mode for cli.",
    )


def add_param_verbose(parser):
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Increase logging verbosity. Use --debug for full debug logs.",
    )


def add_param_config(parser):
    parser.add_argument(
        "--config",
        nargs="+",
        action=AppendToDictAction,
        help=argparse.SUPPRESS,
    )


logging_params = [add_param_verbose, add_param_debug]
base_params = logging_params + [
    add_param_ua,
]


def add_param_archived_only(parser):
    parser.add_argument(
        "--archived-only",
        action="store_true",
        help="Only list archived records.",
    )


def add_param_include_archived(parser):
    parser.add_argument(
        "--include-archived",
        action="store_true",
        help="List both archived records and active records.",
    )


def add_param_output_format(parser):
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=CLIListOutputFormat.JSON,
        help="Output format, accepted values are 'json' and 'table'. Default is 'json'.",
        choices=[CLIListOutputFormat.TABLE, CLIListOutputFormat.JSON],
    )


def add_param_include_others(parser):
    parser.add_argument(
        "--include-others",
        action="store_true",
        help="Get records that are owned by all users.",
    )


def add_param_flow_type(parser):
    parser.add_argument(
        "--type",
        type=str,
        help=(
            f"The type of the flow. Available values are {FlowType.get_all_values()}. "
            f"Default to be None, which means all types included."
        ),
    )


def add_param_flow_name(parser):
    parser.add_argument(
        "-n",
        "--name",
        type=str,
        required=True,
        help="The name of the flow.",
    )
