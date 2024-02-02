# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from azure.cosmos.cosmos_client import CosmosClient
from azure.cosmos.container import ContainerProxy

client_map = {}

def get_client(container_name: str) -> ContainerProxy:
    # Must ensure that client exists
    return client_map[container_name]

def _init_container_client(endpoint: str, database_name: str, container_name: str, resource_url: str, token: str) -> ContainerProxy:
    token_dict = {resource_url: token}
    token_client = CosmosClient(endpoint, token_dict)
    token_db = token_client.get_database_client(database_name)
    container_client = token_db.get_container_client(container_name)
    client_map[container_name] = container_client
    return container_client
