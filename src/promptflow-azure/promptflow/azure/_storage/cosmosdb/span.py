# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict

from azure.cosmos.container import ContainerProxy
from azure.storage.blob import ContainerClient

from promptflow._constants import SpanContextFieldName, SpanEventFieldName, SpanFieldName
from promptflow._sdk.entities._trace import Span as SpanEntity

DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"  # timestamp format e.g. 2021-08-25T00:00:00.000000Z


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
    external_event_data_uris: list = None

    def __init__(self, span: SpanEntity, collection_id: str, created_by: dict) -> None:
        self.name = span.name
        self.context = span.context
        self.kind = span.kind
        self.parent_id = span.parent_id
        # span entity start_time and end_time are datetime objects using utc timezone
        self.start_time = span.start_time.strftime(DATE_FORMAT)
        self.end_time = span.end_time.strftime(DATE_FORMAT) if span.end_time else None
        self.status = span.status
        self.attributes = span.attributes
        # We will remove attributes from events for cosmosdb 2MB size limit.
        # Deep copy to keep original data for LineSummary container.
        self.events = deepcopy(span.events)
        self.links = span.links
        self.resource = span.resource
        self.partition_key = collection_id
        self.collection_id = collection_id
        self.id = span.span_id
        self.created_by = created_by
        self.external_event_data_uris = []
        self.span_json_uri = None

        # covert event time to OTel format
        for event in self.events:
            event[SpanEventFieldName.TIMESTAMP] = datetime.fromisoformat(event[SpanEventFieldName.TIMESTAMP]).strftime(
                DATE_FORMAT
            )

    def persist(self, cosmos_client: ContainerProxy, blob_container_client: ContainerClient, blob_base_uri: str):
        if self.id is None or self.partition_key is None or self.resource is None:
            return

        resource_attributes = self.resource.get(SpanFieldName.ATTRIBUTES, None)
        if resource_attributes is None:
            return

        if blob_container_client is not None and blob_base_uri is not None:
            self._persist_span_json(blob_container_client, blob_base_uri)

        if self.events and blob_container_client is not None and blob_base_uri is not None:
            self._persist_events(blob_container_client, blob_base_uri)

        return cosmos_client.upsert_item(body=self.to_cosmosdb_item())

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v}

    def to_cosmosdb_item(self, attr_value_truncation_length: int = 8 * 1024):
        """
        Convert the object to a dictionary for persistence to CosmosDB.
        Truncate attribute values to avoid exceeding CosmosDB's 2MB size limit.
        """
        item = self.to_dict()  # use to_dict method to get a dictionary representation of the object

        attributes = item.get("attributes")
        if attributes:
            item["attributes"] = {
                k: (v[:attr_value_truncation_length] if isinstance(v, str) else v) for k, v in attributes.items()
            }
        return item

    def _persist_span_json(self, blob_container_client: ContainerClient, blob_base_uri: str):
        """
        Persist the span data as a JSON string in a blob.

        Persisted span should confirm the format of ReadableSpan.to_json().
        https://opentelemetry-python.readthedocs.io/en/latest/_modules/opentelemetry/sdk/trace.html#ReadableSpan.to_json
        """
        # check if span_json_uri is already set
        if self.span_json_uri is not None:
            return

        # persist the span as a json string in a blob
        # align with ReadableSpan.to_json() format
        f_span = {
            "name": self.name,
            "context": self.context,
            "kind": self.kind,
            "parent_id": self.parent_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status,
            "attributes": self.attributes,
            "events": self.events,
            "links": self.links,
            "resource": self.resource,
        }

        span_data = json.dumps(f_span)
        blob_path = self._generate_blob_path(file_name="span.json")
        blob_client = blob_container_client.get_blob_client(blob_path)
        blob_client.upload_blob(span_data, overwrite=True)
        self.span_json_uri = f"{blob_base_uri}{blob_path}"

    def _persist_events(self, blob_container_client: ContainerClient, blob_base_uri: str):
        """
        Persist the event data as a JSON string in a blob.
        """
        for idx, event in enumerate(self.events):
            event_data = json.dumps(event)
            blob_client = blob_container_client.get_blob_client(self._event_path(idx))
            blob_client.upload_blob(event_data, overwrite=True)

            event[SpanEventFieldName.ATTRIBUTES] = {}
            self.external_event_data_uris.append(f"{blob_base_uri}{self._event_path(idx)}")

    TRACE_PATH_PREFIX = ".promptflow/.trace"

    def _event_path(self, idx: int) -> str:
        return self._generate_blob_path(file_name=f"{idx}")

    def _generate_blob_path(self, file_name: str):
        """
        Generate the blob path for the given file name.
        """
        trace_id = self.context[SpanContextFieldName.TRACE_ID]
        return f"{self.TRACE_PATH_PREFIX}/{self.collection_id}/{trace_id}/{self.id}/{file_name}"
