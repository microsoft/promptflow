import argparse


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
                raise Exception("Usage error: {} KEY=VALUE [KEY=VALUE ...]".format(option_string))
        return kwargs


def add_param_yes(parser):
    parser.add_argument(
        "-y",
        "--yes",
        "--assume-yes",
        action="store_true",
        help="Automatic yes to all prompts; assume 'yes' as answer to all prompts and run non-interactively.",
    )


def add_param_flow_name(parser):
    parser.add_argument("--flow", type=str, help="the flow name to create.")


def add_param_entry(parser):
    parser.add_argument("--entry", type=str, help="the entry file.")


def add_param_function(parser):
    parser.add_argument("--function", type=str, help="the function name in entry file.")


def add_param_prompt_template(parser):
    parser.add_argument(
        "--prompt-template", action=AppendToDictAction, help="the prompt template parameter and assignment.", nargs="+"
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


def add_param_environment_variables(parser):
    parser.add_argument(
        "--environment-variables",
        action=AppendToDictAction,
        help="Environment variables to set by specifying a property path and value. Example: --environment-variable "
        'key1="`${my_connection.api_key}" key2="value2". The value reference to connection keys will be resolved '
        "to the actual value, and all environment variables specified will be set into os.environ.",
        nargs="+",
    )


def add_param_input(parser):
    parser.add_argument(
        "--input", type=str, required=True, help="the input file path. Note that we accept jsonl file only for now."
    )


def add_param_env(parser):
    parser.add_argument(
        "--env",
        type=str,
        default=None,
        help="the dotenv file path containing the environment variables to be used in the flow.",
    )


def add_param_output(parser):
    parser.add_argument("--output", type=str, default="outputs", help="the output directory to store the results.")


def add_param_flow(parser):
    parser.add_argument("--flow", type=str, required=True, help="the evaluation flow to be used.")


def add_param_source(parser):
    parser.add_argument("--source", type=str, required=True, help="The flow or run source to be used.")


def add_param_bulk_run_output(parser):
    parser.add_argument("--bulk-run-output", type=str, help="the output directory of the bulk run.")


def add_param_eval_output(parser):
    parser.add_argument("--eval-output", type=str, help="the output file path of the evaluation result.")


def add_param_column_mapping(parser):
    parser.add_argument(
        "--column-mapping", type=str, required=True, help="the column mapping to be used in the evaluation."
    )


def add_param_runtime(parser):
    parser.add_argument(
        "--runtime",
        type=str,
        default="local",
        help="Name of your runtime in Azure ML workspace, will run in cloud when runtime is not none.",
    )


def add_param_connection(parser):
    parser.add_argument("--connection", type=str, help="Name of your connection in Azure ML workspace.")


def add_param_variants(parser):
    parser.add_argument(
        "--variants",
        type=str,
        nargs="+",
        help="the variant run ids to be used in the evaluation. Note that we only support one variant for now.",
        default=[],
    )


def add_param_subscription(parser):
    parser.add_argument(
        "-s",
        "--subscription",
        dest="subscription_id",
        type=str,
        help=("ID of subscription. You can configure the default subscription \n" "using `az account set -s ID`."),
    )


def add_param_resource_group(parser):
    parser.add_argument(
        "-g",
        "--resource-group",
        dest="resource_group_name",
        type=str,
        help=(
            "Name of resource group. You can configure the default group using `az \n"
            "configure --defaults group=<name>`."
        ),
    )


def add_param_workspace(parser):
    parser.add_argument(
        "-w",
        "--workspace-name",
        dest="workspace_name",
        type=str,
        help=(
            "Name of the Azure ML workspace. You can configure the default group using \n"
            "`az configure --defaults workspace=<name>`."
        ),
    )


def add_parser_export(parent_parser, entity_name: str):
    description = f"Export a {entity_name} as a docker image or a package."
    parser = parent_parser.add_parser(
        "export",
        description=description,
        epilog=f"pf {entity_name} export --source <source> --output <output> --format " f"docker|package",
        help=description,
    )
    add_param_source(parser)
    parser.add_argument("--output", "-o", type=str, help="The destination folder path for exported.")
    parser.add_argument("--format", "-f", type=str, help="The format to export in.", choices=["docker", "package"])
    parser.add_argument(
        "--migration-secret",
        type=str,
        help="The secret to encrypt connections data during migration. Need to be provided when "
        "deploying exported docker or package. If not provided, an interactive prompt will "
        "be shown to ask for the secret.",
    )
    parser.add_argument(
        "--migration-secret-file",
        type=str,
        help="Provide migration secret via file to avoid passing it as a command argument. Won't take effect if "
        "--migration-secret is provided.",
    )
    parser.set_defaults(sub_action="export")
