# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

# this file is different from other files in this folder
# functions (APIs) defined in this file follows OTLP 1.1.0
# https://opentelemetry.io/docs/specs/otlp/#otlphttp-request
# to provide OTLP/HTTP endpoint as OTEL collector

import copy
import json
import logging
import traceback
from datetime import datetime
from typing import Callable, List, Optional

from flask import request
from google.protobuf.json_format import MessageToJson
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

from promptflow._constants import CosmosDBContainerName, SpanResourceAttributesFieldName, SpanResourceFieldName
from promptflow._sdk._constants import TRACE_DEFAULT_COLLECTION
from promptflow._sdk._utils import parse_kv_from_pb_attribute
from promptflow._sdk.entities._trace import Span
from promptflow._sdk.operations._trace_operations import TraceOperations
from promptflow._utils.thread_utils import ThreadWithContextVars


def trace_collector(
    get_created_by_info_with_cache: Callable,
    logger: logging.Logger,
    cloud_trace_only: bool = False,
    credential: Optional[object] = None,
):
    """Collect traces from OTLP/HTTP endpoint and write to local/remote storage.

    This function is target to be reused in other places, so pass in get_created_by_info_with_cache and logger to avoid
    app related dependencies.

    :param get_created_by_info_with_cache: A function that retrieves information about the creator of the trace.
    :type get_created_by_info_with_cache: Callable
    :param logger: The logger object used for logging.
    :type logger: logging.Logger
    :param cloud_trace_only: If True, only write trace to cosmosdb and skip local trace. Default is False.
    :type cloud_trace_only: bool
    :param credential: The credential object used to authenticate with cosmosdb. Default is None.
    :type credential: Optional[object]
    """
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
            if SpanResourceAttributesFieldName.COLLECTION not in resource_attributes:
                resource_attributes[SpanResourceAttributesFieldName.COLLECTION] = TRACE_DEFAULT_COLLECTION
            resource = {
                SpanResourceFieldName.ATTRIBUTES: resource_attributes,
                SpanResourceFieldName.SCHEMA_URL: resource_span.schema_url,
            }
            for scope_span in resource_span.scope_spans:
                for span in scope_span.spans:
                    # TODO: persist with batch
                    span: Span = TraceOperations._parse_protobuf_span(span, resource=resource, logger=logger)
                    if not cloud_trace_only:
                        all_spans.append(copy.deepcopy(span))
                        span._persist()
                        logger.debug("Persisted trace id: %s, span id: %s", span.trace_id, span.span_id)
                    else:
                        all_spans.append(span)

        if cloud_trace_only:
            # If we only trace to cloud, we should make sure the data writing is success before return.
            _try_write_trace_to_cosmosdb(
                all_spans, get_created_by_info_with_cache, logger, credential, is_cloud_trace=True
            )
        else:
            # Create a new thread to write trace to cosmosdb to avoid blocking the main thread
            ThreadWithContextVars(
                target=_try_write_trace_to_cosmosdb,
                args=(all_spans, get_created_by_info_with_cache, logger, credential, False),
            ).start()
        return "Traces received", 200

    # JSON protobuf encoding
    elif "application/json" in content_type:
        raise NotImplementedError


def _try_write_trace_to_cosmosdb(
    all_spans: List[Span],
    get_created_by_info_with_cache: Callable,
    logger: logging.Logger,
    credential: Optional[object] = None,
    is_cloud_trace: bool = False,
):
    if not all_spans:
        return
    try:
        first_span = all_spans[0]
        span_resource = first_span.resource
        resource_attributes = span_resource.get(SpanResourceFieldName.ATTRIBUTES, {})
        subscription_id = resource_attributes.get(SpanResourceAttributesFieldName.SUBSCRIPTION_ID, None)
        resource_group_name = resource_attributes.get(SpanResourceAttributesFieldName.RESOURCE_GROUP_NAME, None)
        workspace_name = resource_attributes.get(SpanResourceAttributesFieldName.WORKSPACE_NAME, None)
        if subscription_id is None or resource_group_name is None or workspace_name is None:
            logger.debug("Cannot find workspace info in span resource, skip writing trace to cosmosdb.")
            return

        logger.info(f"Start writing trace to cosmosdb, total spans count: {len(all_spans)}.")
        start_time = datetime.now()

        from promptflow.azure._storage.cosmosdb.client import get_client
        from promptflow.azure._storage.cosmosdb.collection import CollectionCosmosDB
        from promptflow.azure._storage.cosmosdb.span import Span as SpanCosmosDB
        from promptflow.azure._storage.cosmosdb.summary import Summary

        # Load span, collection and summary clients first time may slow.
        # So, we load clients in parallel for warm up.
        span_client_thread = ThreadWithContextVars(
            target=get_client,
            args=(CosmosDBContainerName.SPAN, subscription_id, resource_group_name, workspace_name, credential),
        )
        span_client_thread.start()

        collection_client_thread = ThreadWithContextVars(
            target=get_client,
            args=(CosmosDBContainerName.COLLECTION, subscription_id, resource_group_name, workspace_name, credential),
        )
        collection_client_thread.start()

        line_summary_client_thread = ThreadWithContextVars(
            target=get_client,
            args=(CosmosDBContainerName.LINE_SUMMARY, subscription_id, resource_group_name, workspace_name, credential),
        )
        line_summary_client_thread.start()

        # Load created_by info first time may slow. So, we load it in parallel for warm up.
        created_by_thread = ThreadWithContextVars(target=get_created_by_info_with_cache)
        created_by_thread.start()

        # Get default blob may be slow. So, we have a cache for default datastore.
        from promptflow.azure._storage.blob.client import get_datastore_container_client

        blob_container_client, blob_base_uri = get_datastore_container_client(
            logger=logger,
            subscription_id=subscription_id,
            resource_group_name=resource_group_name,
            workspace_name=workspace_name,
            credential=credential,
        )

        span_client_thread.join()
        collection_client_thread.join()
        line_summary_client_thread.join()
        created_by_thread.join()

        created_by = get_created_by_info_with_cache()
        collection_client = get_client(
            CosmosDBContainerName.COLLECTION, subscription_id, resource_group_name, workspace_name, credential
        )

        collection_db = CollectionCosmosDB(first_span, is_cloud_trace, created_by)
        collection_db.create_collection_if_not_exist(collection_client)
        # For runtime, collection id is flow id for test, batch run id for batch run.
        # For local, collection id is collection name + user id for non batch run, batch run id for batch run.
        # We assign it to LineSummary and Span and use it as partition key.
        collection_id = collection_db.collection_id

        for span in all_spans:
            span_client = get_client(
                CosmosDBContainerName.SPAN, subscription_id, resource_group_name, workspace_name, credential
            )
            result = SpanCosmosDB(span, collection_id, created_by).persist(
                span_client, blob_container_client, blob_base_uri
            )
            # None means the span already exists, then we don't need to persist the summary also.
            if result is not None:
                line_summary_client = get_client(
                    CosmosDBContainerName.LINE_SUMMARY,
                    subscription_id,
                    resource_group_name,
                    workspace_name,
                    credential,
                )
                Summary(span, collection_id, created_by, logger).persist(line_summary_client)
        collection_db.update_collection_updated_at_info(collection_client)
        logger.info(
            (
                f"Finish writing trace to cosmosdb, total spans count: {len(all_spans)}."
                f" Duration {datetime.now() - start_time}."
            )
        )

    except Exception as e:
        stack_trace = traceback.format_exc()
        logger.error(f"Failed to write trace to cosmosdb: {e}, stack trace is {stack_trace}")
        return
