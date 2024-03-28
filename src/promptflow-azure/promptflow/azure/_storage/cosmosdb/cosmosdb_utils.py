from dataclasses import asdict

from azure.cosmos import ContainerProxy
from azure.cosmos.exceptions import CosmosResourceExistsError, CosmosResourceNotFoundError


def safe_create_cosmosdb_item(client: ContainerProxy, dataclass_item):
    try:
        # Attempt to read the item using its ID and partition key
        client.read_item(item=dataclass_item.id, partition_key=dataclass_item.partition_key)
    except CosmosResourceNotFoundError:
        # Only create for not exist situation.
        try:
            client.create_item(body=asdict(dataclass_item))
        except CosmosResourceExistsError:
            # Ignore conflict error.
            return
