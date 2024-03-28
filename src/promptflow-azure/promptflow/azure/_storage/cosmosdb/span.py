# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Any, Dict

from promptflow._constants import SpanFieldName, SpanResourceAttributesFieldName
from promptflow._sdk._constants import TRACE_DEFAULT_COLLECTION
from promptflow._sdk.entities._trace import Span as SpanEntity


class Span:

    name: str = None
    context: dict = None
    kind: str = None
    parent_id: str = None
    start_time: str = None
    end_time: str = None
    status: dict = None
    attributes: dict = None
    events: list = None
    links: list = None
    resource: dict = None
    id: str = None
    partition_key: str = None
    collection_id: str = None
    created_by: dict = None

    def __init__(self, span: SpanEntity, collection_id: str, created_by: dict) -> None:
        self.name = span.name
        self.context = span.context
        self.kind = span.kind
        self.parent_id = span.parent_id
        self.start_time = span.start_time.isoformat()
        self.end_time = span.end_time.isoformat()
        self.status = span.status
        self.attributes = span.attributes
        self.events = span.events
        self.links = span.links
        self.resource = span.resource
        self.partition_key = span.resource.get(SpanResourceAttributesFieldName.COLLECTION, TRACE_DEFAULT_COLLECTION)
        self.collection_id = collection_id
        self.id = span.span_id
        self.created_by = created_by

    def persist(self, client):
        if self.id is None or self.partition_key is None or self.resource is None:
            return

        resource_attributes = self.resource.get(SpanFieldName.ATTRIBUTES, None)
        if resource_attributes is None:
            return

        from azure.cosmos.exceptions import CosmosResourceExistsError

        try:
            return client.create_item(body=self.to_dict())
        except CosmosResourceExistsError:
            return None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v}
