# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

# this file is different from other files in this folder
# functions (APIs) defined in this file follows OTLP 1.1.0
# https://opentelemetry.io/docs/specs/otlp/#otlphttp-request
# to provide OTLP/HTTP endpoint as OTEL collector

import json
import traceback
from datetime import datetime

from flask import current_app, request
from google.protobuf.json_format import MessageToJson
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

from promptflow._constants import (
    CosmosDBContainerName,
    SpanFieldName,
    SpanResourceAttributesFieldName,
    SpanResourceFieldName,
)
from promptflow._sdk._utils import parse_kv_from_pb_attribute
from promptflow._sdk.entities._trace import Span
from promptflow._utils.thread_utils import ThreadWithContextVars


def trace_collector():
    content_type = request.headers.get("Content-Type")
    # binary protobuf encoding
    if "application/x-protobuf" in content_type:
        traces_request = ExportTraceServiceRequest()
        traces_request.ParseFromString(request.data)
        all_spans = []
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
                    all_spans.append(span)

        # Create a new thread to write trace to cosmosdb to avoid blocking the main thread
        ThreadWithContextVars(target=_try_write_trace_to_cosmosdb, args=(all_spans,)).start()
        return "Traces received", 200

    # JSON protobuf encoding
    elif "application/json" in content_type:
        raise NotImplementedError


def _try_write_trace_to_cosmosdb(all_spans):
    if not all_spans:
        return
    try:
        span_resource = all_spans[0]._content.get(SpanFieldName.RESOURCE, {})
        resource_attributes = span_resource.get(SpanResourceFieldName.ATTRIBUTES, {})
        subscription_id = resource_attributes.get(SpanResourceAttributesFieldName.SUBSCRIPTION_ID, None)
        resource_group_name = resource_attributes.get(SpanResourceAttributesFieldName.RESOURCE_GROUP_NAME, None)
        workspace_name = resource_attributes.get(SpanResourceAttributesFieldName.WORKSPACE_NAME, None)
        if subscription_id is None or resource_group_name is None or workspace_name is None:
            current_app.logger.debug("Cannot find workspace info in span resource, skip writing trace to cosmosdb.")
            return

        current_app.logger.info(f"Start writing trace to cosmosdb, total spans count: {len(all_spans)}.")
        start_time = datetime.now()
        from promptflow._sdk._service.app import CREATED_BY_FOR_LOCAL_TO_CLOUD_TRACE
        from promptflow.azure._storage.cosmosdb.client import get_client
        from promptflow.azure._storage.cosmosdb.span import Span as SpanCosmosDB
        from promptflow.azure._storage.cosmosdb.summary import Summary

        # Load span and summary clients first time may slow.
        # So, we load 2 client in parallel for warm up.
        span_thread = ThreadWithContextVars(
            target=get_client, args=(CosmosDBContainerName.SPAN, subscription_id, resource_group_name, workspace_name)
        )
        span_thread.start()

        get_client(CosmosDBContainerName.LINE_SUMMARY, subscription_id, resource_group_name, workspace_name)

        span_thread.join()

        for span in all_spans:
            span_client = get_client(CosmosDBContainerName.SPAN, subscription_id, resource_group_name, workspace_name)
            result = SpanCosmosDB(span, CREATED_BY_FOR_LOCAL_TO_CLOUD_TRACE).persist(span_client)
            # None means the span already exists, then we don't need to persist the summary also.
            if result is not None:
                line_summary_client = get_client(
                    CosmosDBContainerName.LINE_SUMMARY, subscription_id, resource_group_name, workspace_name
                )
                Summary(span, CREATED_BY_FOR_LOCAL_TO_CLOUD_TRACE).persist(line_summary_client)
        current_app.logger.info(
            (
                f"Finish writing trace to cosmosdb, total spans count: {len(all_spans)}."
                f" Duration {datetime.now() - start_time}."
            )
        )

    except Exception as e:
        stack_trace = traceback.format_exc()
        current_app.logger.error(f"Failed to write trace to cosmosdb: {e}, stack trace is {stack_trace}")
        return
