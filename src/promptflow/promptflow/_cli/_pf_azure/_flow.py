# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from os import PathLike
from pathlib import Path
from typing import IO, AnyStr, Union

from promptflow._cli._pf_azure._utils import _get_azure_pf_client
from promptflow._cli._utils import _set_workspace_argument_for_subparsers
from promptflow.azure._load_functions import load_flow


def add_parser_flow(subparsers):
    """Add flow parser to the pf subparsers."""
    flow_parser = subparsers.add_parser(
        "flow",
        description="Manage flows for promptflow.",
        help="pf flow",
    )
    _set_workspace_argument_for_subparsers(flow_parser)
    flow_subparsers = flow_parser.add_subparsers()
    add_parser_flow_create(flow_subparsers)
    # add_parser_flow_get(flow_subparsers)
    add_parser_flow_list(flow_subparsers)
    # add_parser_flow_delete(flow_subparsers)
    add_parser_flow_download(flow_subparsers)
    flow_parser.set_defaults(action="flow")


def add_parser_flow_create(subparsers):
    """Add flow create parser to the pf flow subparsers."""
    create_parser = subparsers.add_parser("create", description="Create a flow for promptflow.", help="pf flow create")
    _set_workspace_argument_for_subparsers(create_parser)
    create_parser.add_argument("--source", type=str, help="Source folder of the flow to create.")
    create_parser.set_defaults(sub_action="create")


def add_parser_flow_list(subparsers):
    """Add flow list parser to the pf flow subparsers."""
    list_parser = subparsers.add_parser("list", description="List flows for promptflow.", help="pf flow list")
    _set_workspace_argument_for_subparsers(list_parser)
    list_parser.set_defaults(sub_action="list")


def add_parser_flow_download(subparsers):
    """Add flow download parser to the pf flow subparsers."""
    download_parser = subparsers.add_parser(
        "download", description="Download a flow from file share to local.", help="pf flow download"
    )
    _set_workspace_argument_for_subparsers(download_parser)
    download_parser.add_argument("--source", type=str, help="The flow folder path on file share to download.")
    download_parser.add_argument("--destination", "-d", type=str, help="The destination folder path to download.")
    download_parser.set_defaults(sub_action="download")


def _get_flow_operation(subscription_id, resource_group, workspace_name):
    pf_client = _get_azure_pf_client(subscription_id, resource_group, workspace_name)
    return pf_client._flows


def create_flow(
    source: Union[str, PathLike, IO[AnyStr]],
    workspace_name: str,
    resource_group: str,
    subscription_id: str,
):
    """Create a flow for promptflow."""
    source = Path(source).resolve().absolute()
    if not source.exists():
        raise FileNotFoundError(f"Source folder {str(source)!r} does not exist.")
    if not source.is_dir():
        raise ValueError(f"Source path {str(source)!r} should be a folder, got a file.")
    flow_entity = load_flow(source)
    flow_operations = _get_flow_operation(subscription_id, resource_group, workspace_name)
    flow_draft = flow_operations._create_or_update(flow_entity)
    print(f"Successfully created flow {flow_draft.flow_name!r} with flow id {flow_draft.flow_id!r}.")
    return flow_draft


def list_flows(
    workspace_name: str,
    resource_group: str,
    subscription_id: str,
):
    """List flows for promptflow."""
    flow_operations = _get_flow_operation(subscription_id, resource_group, workspace_name)
    flows = flow_operations._list()
    flow_count = len(flows)
    print(f"Collected {flow_count} flows.")
    if flow_count > 0:
        print("=================== Flows ===================")
        for flow in flows:
            print(f"Name: {flow.name!r}, owner: {flow.owner!r}, flow_id: {flow.flow_id!r}")


def download_flow(
    source: str,
    destination: str,
    workspace_name: str,
    resource_group: str,
    subscription_id: str,
):
    """Download a flow from file share to local."""
    flow_operations = _get_flow_operation(subscription_id, resource_group, workspace_name)
    flow_operations.download(source, destination)
    print(f"Successfully download flow from file share path {source!r} to {destination!r}.")
