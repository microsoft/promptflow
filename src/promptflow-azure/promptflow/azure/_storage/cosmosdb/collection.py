# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict

from azure.cosmos import ContainerProxy

from promptflow._constants import SpanAttributeFieldName, SpanResourceAttributesFieldName, SpanResourceFieldName
from promptflow._sdk._constants import TRACE_DEFAULT_COLLECTION, CreatedByFieldName
from promptflow._sdk.entities._trace import Span
from promptflow.azure._storage.cosmosdb.cosmosdb_utils import safe_create_cosmosdb_item


@dataclass
class Collection:
    id: str  # Collection id for cosmosDB query, usually hide from customer
    partition_key: str
    name: str  # Display name for customer facing UI
    created_at: int
    updated_at: int
    created_by: Dict[str, Any]
    location: int


class LocationType(int, Enum):
    LOCAL = 0
    CLOUD = 1


def generate_collection_id_by_name_and_created_by(name: str, created_by: Dict[str, Any]) -> str:
    return f"{name}_{created_by[CreatedByFieldName.OBJECT_ID]}"


class CollectionCosmosDB:
    def __init__(self, span: Span, is_cloud_trace: bool, created_by: Dict[str, Any]):
        self.span = span
        self.created_by = created_by
        self.location = LocationType.CLOUD if is_cloud_trace else LocationType.LOCAL
        resource_attributes = span.resource.get(SpanResourceFieldName.ATTRIBUTES, {})
        self.collection_name = resource_attributes.get(
            SpanResourceAttributesFieldName.COLLECTION, TRACE_DEFAULT_COLLECTION
        )
        span_attributes = self.span.attributes
        if SpanAttributeFieldName.BATCH_RUN_ID in span_attributes:
            self.collection_id = span_attributes[SpanAttributeFieldName.BATCH_RUN_ID]
        else:
            self.collection_id = (
                resource_attributes[SpanResourceAttributesFieldName.COLLECTION_ID]
                if is_cloud_trace
                else generate_collection_id_by_name_and_created_by(self.collection_name, created_by)
            )

    def create_collection_if_not_exist(self, client: ContainerProxy):
        span_attributes = self.span.attributes
        # For batch run, ignore collection operation
        if SpanAttributeFieldName.BATCH_RUN_ID in span_attributes:
            return

        item = Collection(
            id=self.collection_id,
            partition_key=self.collection_id,
            name=self.collection_name,
            created_at=int(time.time()),
            updated_at=int(time.time()),
            created_by=self.created_by,
            location=self.location,
        )
        safe_create_cosmosdb_item(client, item)
        # Update name if customer change flow display name
        patch_operations = [{"op": "replace", "path": "/name", "value": self.collection_name}]
        return client.patch_item(
            item=self.collection_id, partition_key=self.collection_id, patch_operations=patch_operations
        )

    def update_collection_updated_at_info(self, client: ContainerProxy):
        span_attributes = self.span.attributes
        # For batch run, ignore collection operation
        if SpanAttributeFieldName.BATCH_RUN_ID in span_attributes:
            return

        patch_operations = [{"op": "replace", "path": "/updated_at", "value": int(time.time())}]
        return client.patch_item(
            item=self.collection_id, partition_key=self.collection_id, patch_operations=patch_operations
        )
