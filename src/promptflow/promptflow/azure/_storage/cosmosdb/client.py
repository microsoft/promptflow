# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import ast
import datetime
import os
import threading
from typing import Optional

from azure.cosmos.container import ContainerProxy
from azure.cosmos.cosmos_client import CosmosClient
from flask import current_app

client_map = {}
_thread_lock = threading.Lock()
_token_timeout = 60 * 9  # Timeout is 10 minutes, set expire at 9 minutes for update


def get_client_with_workspace_info(container_name: str, workspace_info: dict) -> ContainerProxy:

    # Use workspace_info to get the client may not a good idea, just for test.
    subscription_id = workspace_info.get("subscription_id", os.environ.get("pf_test_subscription_id"))
    resource_group_name = workspace_info.get("resource_group_name", os.environ.get("pf_test_resource_group_name"))
    workspace_name = workspace_info.get("workspace_name", os.environ.get("pf_test_workspace_name"))
    if subscription_id is None or resource_group_name is None or workspace_name is None:
        current_app.logger.info("No workspace info found. Skip getting client.")
        return None
    current_app.logger.info(f"sub id:{subscription_id}  rg:{resource_group_name}  ws:{workspace_name}")
    return get_client(container_name, subscription_id, resource_group_name, workspace_name)


def get_client(
    container_name: str, subscription_id: str, resource_group_name: str, workspace_name: str
) -> ContainerProxy:
    # Must ensure that client exists
    client_key = _get_db_client_key(container_name, subscription_id, resource_group_name, workspace_name)
    container_client = _get_client_from_map(client_key)
    if container_client is None:
        with _thread_lock:
            container_client = _get_client_from_map(client_key)
            if container_client is None:
                token = _get_resource_token(container_name, subscription_id, resource_group_name, workspace_name)
                container_client = _init_container_client(
                    endpoint=token["accountEndpoint"],
                    database_name=token["databaseName"],
                    container_name=token["containerName"],
                    resource_url=token["resourceUrl"],
                    token=token["resourceToken"],
                )
                client_map[client_key] = {
                    "expire_at": datetime.datetime.now() + datetime.timedelta(0, _token_timeout),
                    "client": container_client,
                }
    return container_client


def _get_client_from_map(client_key: str) -> Optional[ContainerProxy]:
    client = client_map.get(client_key, None)
    if client is None:
        return None

    if client["expire_at"] < datetime.datetime.now():
        return client["client"]

    return None


def _get_resource_token(
    container_name: str, subscription_id: str, resource_group_name: str, workspace_name: str
) -> object:
    from azure.identity import DefaultAzureCredential

    from promptflow.azure import PFClient

    pf_client = PFClient(
        credential=DefaultAzureCredential(),
        subscription_id=subscription_id,
        resource_group_name=resource_group_name,
        workspace_name=workspace_name,
    )

    token_resp = pf_client._traces._get_cosmos_db_token(container_name=container_name, acquire_write=True)
    # Support json with single quotes
    return ast.literal_eval(token_resp)


def _init_container_client(
    endpoint: str, database_name: str, container_name: str, resource_url: str, token: str
) -> ContainerProxy:
    token_dict = {resource_url: token}
    token_client = CosmosClient(endpoint, token_dict)
    token_db = token_client.get_database_client(database_name)
    container_client = token_db.get_container_client(container_name)
    return container_client


def _get_db_client_key(container_name: str, subscription_id: str, resource_group_name: str, workspace_name: str) -> str:
    return f"{subscription_id}_{resource_group_name}_{workspace_name}_{container_name}"
