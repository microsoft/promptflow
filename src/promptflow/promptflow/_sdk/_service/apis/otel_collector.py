# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from flask import request
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

from promptflow._sdk.entities._otel import Span


def trace_collector():
    traces_request = ExportTraceServiceRequest()
    traces_request.ParseFromString(request.data)
    for resource_span in traces_request.resource_spans:
        for scope_span in resource_span.scope_spans:
            for span in scope_span.spans:
                entity = Span._from_protobuf_object(span)
                entity.persist()

    return "Traces received", 200
