# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

# this file is different from other files in this folder
# functions (APIs) defined in this file follows OTLP 1.1.0
# https://opentelemetry.io/docs/specs/otlp/#otlphttp-request
# to provide OTLP/HTTP endpoint as OTEL collector

import json
import os

from flask import request
from google.protobuf.json_format import MessageToJson
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

from promptflow._constants import CosmosDBContainerName, SpanResourceFieldName
from promptflow._sdk._utils import parse_kv_from_pb_attribute
from promptflow._sdk.entities._trace import Span


# Check if the AML workspace is configured
# If not, don't import any AML related modules
def _is_workspace_configured():
    subscription_id, resource_group_name, workspace_name = _get_workspace_info()
    return subscription_id is not None and resource_group_name is not None and workspace_name is not None


def _get_workspace_info():
    # TODO: Change to workspace triad
    return (
        os.environ.get("pf_test_subscription_id"),
        os.environ.get("pf_test_resource_group_name"),
        os.environ.get("pf_test_workspace_name"),
    )


def trace_collector():
    content_type = request.headers.get("Content-Type")
    if _is_workspace_configured():
        from promptflow.azure._storage.cosmosdb.client import get_client

        subscription_id, resource_group_name, workspace_name = _get_workspace_info()
        span_client = get_client(CosmosDBContainerName.SPAN, subscription_id, resource_group_name, workspace_name)
        line_summary_client = get_client(
            CosmosDBContainerName.LINE_SUMMARY, subscription_id, resource_group_name, workspace_name
        )
    # binary protobuf encoding
    if "application/x-protobuf" in content_type:
        traces_request = ExportTraceServiceRequest()
        traces_request.ParseFromString(request.data)
        for resource_span in traces_request.resource_spans:
            resource_attributes = dict()
            for attribute in resource_span.resource.attributes:
                attribute_dict = json.loads(MessageToJson(attribute))
                attr_key, attr_value = parse_kv_from_pb_attribute(attribute_dict)
                resource_attributes[attr_key] = attr_value
            resource = {
                SpanResourceFieldName.ATTRIBUTES: resource_attributes,
                SpanResourceFieldName.SCHEMA_URL: resource_span.schema_url,
            }
            for scope_span in resource_span.scope_spans:
                for span in scope_span.spans:
                    # TODO: persist with batch
                    span = Span._from_protobuf_object(span, resource=resource)
                    span._persist()
                    if _is_workspace_configured():
                        _write_trace_to_cosmosdb(span, line_summary_client, span_client)
        return "Traces received", 200

    # JSON protobuf encoding
    elif "application/json" in content_type:
        raise NotImplementedError


def _write_trace_to_cosmosdb(span: Span, line_summary_client, span_client):
    from promptflow.azure._storage.cosmosdb.span import Span as SpanCosmosDB
    from promptflow.azure._storage.cosmosdb.summary import Summary

    if line_summary_client and span_client:
        result = SpanCosmosDB(span).persist(span_client)
        # None means the span already exists, then we don't need to persist the summary also.
        if result is not None:
            Summary(span).persist(line_summary_client)
