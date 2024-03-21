# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Any, Dict

from promptflow._constants import SpanFieldName
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
    created_by: dict = None

    def __init__(self, span: SpanEntity, created_by: dict) -> None:
        self.name = span.name
        self.context = span._content[SpanFieldName.CONTEXT]
        self.kind = span._content[SpanFieldName.KIND]
        self.parent_id = span.parent_span_id
        self.start_time = span._content[SpanFieldName.START_TIME]
        self.end_time = span._content[SpanFieldName.END_TIME]
        self.status = span._content[SpanFieldName.STATUS]
        self.attributes = span._content[SpanFieldName.ATTRIBUTES]
        self.events = span._content[SpanFieldName.EVENTS]
        self.links = span._content[SpanFieldName.LINKS]
        self.resource = span._content[SpanFieldName.RESOURCE]
        self.partition_key = span.session_id
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
