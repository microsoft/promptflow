# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import ast
import datetime
import threading
from typing import Callable

client_map = {}
_thread_lock = threading.Lock()
_container_lock_dict = {}
_token_timeout = 60 * 4  # Will try to refresh token if exceed 4 minutes


def get_client(
    container_name: str,
    subscription_id: str,
    resource_group_name: str,
    workspace_name: str,
    get_credential: Callable,
):
    client_key = _get_db_client_key(container_name, subscription_id, resource_group_name, workspace_name)
    container_client = _get_client_from_map(client_key)
    if container_client is None:
        # Use lock to avoid too many requests for same container token
        container_lock = _get_container_lock(client_key)
        with container_lock:
            container_client = _get_client_from_map(client_key)
            if container_client is None:
                credential = get_credential()
                token = _get_resource_token(
                    container_name, subscription_id, resource_group_name, workspace_name, credential
                )
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


def _get_client_from_map(client_key: str):
    client = client_map.get(client_key, None)
    if client is None:
        return None

    if client["expire_at"] > datetime.datetime.now():
        return client["client"]

    return None


def _get_container_lock(client_key: str):
    with _thread_lock:
        container_lock = _container_lock_dict.get(client_key, None)
        if container_lock is None:
            container_lock = threading.Lock()
            _container_lock_dict[client_key] = container_lock
    return container_lock


def _get_resource_token(
    container_name: str,
    subscription_id: str,
    resource_group_name: str,
    workspace_name: str,
    credential,
) -> object:
    from promptflow.azure import PFClient

    # The default connection_time and read_timeout are both 300s.
    # The get token operation should be fast, so we set a short timeout.
    pf_client = PFClient(
        credential=credential,
        subscription_id=subscription_id,
        resource_group_name=resource_group_name,
        workspace_name=workspace_name,
        connection_timeout=15.0,
        read_timeout=30.0,
    )

    token_resp = pf_client._traces._get_cosmos_db_token(container_name=container_name, acquire_write=True)
    # Support json with single quotes
    return ast.literal_eval(token_resp)


def _init_container_client(endpoint: str, database_name: str, container_name: str, resource_url: str, token: str):
    from azure.cosmos.cosmos_client import CosmosClient

    token_dict = {resource_url: token}
    token_client = CosmosClient(endpoint, token_dict)
    token_db = token_client.get_database_client(database_name)
    container_client = token_db.get_container_client(container_name)
    return container_client


def _get_db_client_key(container_name: str, subscription_id: str, resource_group_name: str, workspace_name: str) -> str:
    # Azure name allow hyphens and underscores. User @ to avoid possible conflict.
    return f"{subscription_id}@{resource_group_name}@{workspace_name}@{container_name}"
