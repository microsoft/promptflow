# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import argparse
import json
from typing import Dict, List

from promptflow._cli._params import (
    add_param_archived_only,
    add_param_flow_name,
    add_param_flow_type,
    add_param_include_archived,
    add_param_include_others,
    add_param_max_results,
    add_param_output_format,
    add_param_set,
    base_params,
)
from promptflow._cli._utils import (
    _output_result_list_with_format,
    _set_workspace_argument_for_subparsers,
    activate_action,
)
from promptflow._sdk._constants import AzureFlowSource, get_list_view_type
from promptflow.azure._cli._utils import _get_azure_pf_client
from promptflow.azure._entities._flow import Flow


def add_parser_flow(subparsers):
    """Add flow parser to the pf subparsers."""
    flow_parser = subparsers.add_parser(
        "flow",
        description="Manage flows for prompt flow.",
        help="Manage prompt flows.",
    )
    flow_subparsers = flow_parser.add_subparsers()
    add_parser_flow_create(flow_subparsers)
    add_parser_flow_update(flow_subparsers)
    add_parser_flow_show(flow_subparsers)
    add_parser_flow_list(flow_subparsers)
    flow_parser.set_defaults(action="flow")


def add_parser_flow_create(subparsers):
    """Add flow create parser to the pf flow subparsers."""
    epilog = """
Use "--set" to set flow properties like:
    display_name: Flow display name that will be created in remote. Default to be flow folder name + timestamp if not specified.
    type: Flow type. Default to be "standard" if not specified. Available types are: "standard", "evaluation", "chat".
    description: Flow description. e.g. "--set description=<description>."
    tags: Flow tags. e.g. "--set tags.key1=value1 tags.key2=value2."

Note:
    In "--set" parameter, if the key name consists of multiple words, use snake-case instead of kebab-case. e.g. "--set display_name=<flow-display-name>"

Examples:

# Create a flow to azure portal with local flow folder.
pfazure flow create --flow <flow-folder-path> --set display_name=<flow-display-name> type=<flow-type>

# Create a flow with more properties
pfazure flow create --flow <flow-folder-path> --set display_name=<flow-display-name> type=<flow-type> description=<flow-description> tags.key1=value1 tags.key2=value2
"""  # noqa: E501
    add_param_source = lambda parser: parser.add_argument(  # noqa: E731
        "--flow", type=str, help="Source folder of the flow."
    )
    add_params = [
        add_param_source,
        add_param_set,
        _set_workspace_argument_for_subparsers,
    ] + base_params

    activate_action(
        name="create",
        description="A CLI tool to create a flow to Azure.",
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Create a flow to Azure with local flow folder.",
        action_param_name="sub_action",
    )


def add_parser_flow_update(subparsers):
    """Add flow update parser to the pf flow subparsers."""
    epilog = """
Use "--set" to set flow properties that you want to update. Supported properties are: [display_name, description, tags].

Note:
    1. In "--set" parameter, if the key name consists of multiple words, use snake-case instead of kebab-case. e.g. "--set display_name=<flow-display-name>"
    2. Parameter flow is required to update a flow. It's a guid that can be found from 2 ways:
        a. After creating a flow to azure, it can be found in the printed message in "name" attribute.
        b. Open a flow in azure portal, the guid is in the url. e.g. https://ml.azure.com/prompts/flow/<workspace-id>/<flow-name>/xxx

Examples:

# Update a flow display name
pfazure flow update --flow <flow-name> --set display_name=<flow-display-name>
"""  # noqa: E501

    add_param_source = lambda parser: parser.add_argument(  # noqa: E731
        "--flow", type=str, help="Flow name to be updated which is a guid."
    )
    add_params = [
        add_param_source,
        add_param_set,
        _set_workspace_argument_for_subparsers,
    ] + base_params

    activate_action(
        name="update",
        description="A CLI tool to update a flow's metadata on Azure.",
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Update a flow's metadata on azure.",
        action_param_name="sub_action",
    )


def add_parser_flow_list(subparsers):
    """Add flow list parser to the pf flow subparsers."""
    epilog = """
Examples:

# List flows:
pfazure flow list
# List most recent 10 runs status:
pfazure flow list --max-results 10
# List active and archived flows:
pfazure flow list --include-archived
# List archived flow only:
pfazure flow list --archived-only
# List all flows as table:
pfazure flow list --output table
# List flows with specific type:
pfazure flow list --type standard
# List flows that are owned by all users:
pfazure flow list --include-others
"""
    add_params = [
        add_param_max_results,
        add_param_include_others,
        add_param_flow_type,
        add_param_archived_only,
        add_param_include_archived,
        add_param_output_format,
        _set_workspace_argument_for_subparsers,
    ] + base_params

    activate_action(
        name="list",
        description="List flows for promptflow.",
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="pfazure flow list",
        action_param_name="sub_action",
    )


def add_parser_flow_show(subparsers):
    """Add flow get parser to the pf flow subparsers."""
    epilog = """
Examples:

# Get flow:
pfazure flow show --name <flow-name>
"""
    add_params = [add_param_flow_name, _set_workspace_argument_for_subparsers] + base_params

    activate_action(
        name="show",
        description="Show a flow from Azure.",
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="pfazure flow show",
        action_param_name="sub_action",
    )


def add_parser_flow_download(subparsers):
    """Add flow download parser to the pf flow subparsers."""
    add_param_source = lambda parser: parser.add_argument(  # noqa: E731
        "--source", type=str, help="The flow folder path on file share to download."
    )
    add_param_destination = lambda parser: parser.add_argument(  # noqa: E731
        "--destination", "-d", type=str, help="The destination folder path to download."
    )
    add_params = [
        _set_workspace_argument_for_subparsers,
        add_param_source,
        add_param_destination,
    ] + base_params

    activate_action(
        name="download",
        description="Download a flow from file share to local.",
        epilog=None,
        add_params=add_params,
        subparsers=subparsers,
        help_message="pf flow download",
        action_param_name="sub_action",
    )


def dispatch_flow_commands(args: argparse.Namespace):
    if args.sub_action == "create":
        create_flow(args)
    elif args.sub_action == "show":
        show_flow(args)
    elif args.sub_action == "list":
        list_flows(args)
    elif args.sub_action == "update":
        update_flow(args)


def _get_flow_operation(subscription_id, resource_group, workspace_name):
    pf_client = _get_azure_pf_client(subscription_id, resource_group, workspace_name)
    return pf_client._flows


def create_flow(args: argparse.Namespace):
    """Create a flow for promptflow."""
    pf = _get_azure_pf_client(args.subscription, args.resource_group, args.workspace_name, debug=args.debug)
    params = _parse_flow_metadata_args(args.params_override)
    pf.flows.create_or_update(flow=args.flow, **params)


def update_flow(args: argparse.Namespace):
    """Update a flow for promptflow."""
    pf = _get_azure_pf_client(args.subscription, args.resource_group, args.workspace_name, debug=args.debug)
    params = _parse_flow_metadata_args(args.params_override)
    flow_object = Flow(name=args.flow, flow_source=AzureFlowSource.PF_SERVICE)
    pf.flows.create_or_update(flow=flow_object, **params)


def show_flow(args: argparse.Namespace):
    """Get a flow for promptflow."""
    pf = _get_azure_pf_client(args.subscription, args.resource_group, args.workspace_name, debug=args.debug)
    flow = pf.flows.get(args.name)
    print(json.dumps(flow._to_dict(), indent=4))


def list_flows(args: argparse.Namespace):
    """List flows for promptflow."""
    pf = _get_azure_pf_client(args.subscription, args.resource_group, args.workspace_name, debug=args.debug)
    flows = pf.flows.list(
        max_results=args.max_results,
        include_others=args.include_others,
        flow_type=args.type,
        list_view_type=get_list_view_type(args.archived_only, args.include_archived),
    )
    flow_list = [flow._to_dict() for flow in flows]
    _output_result_list_with_format(flow_list, args.output)


def _parse_flow_metadata_args(params: List[Dict[str, str]]) -> Dict:
    result, tags = {}, {}
    if not params:
        return result
    for param in params:
        for k, v in param.items():
            if k.startswith("tags."):
                tag_key = k.replace("tags.", "")
                tags[tag_key] = v
                continue
            result[k] = v
    if tags:
        result["tags"] = tags
    return result
