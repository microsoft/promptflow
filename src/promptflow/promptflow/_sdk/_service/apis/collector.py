# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

# this file is different from other files in this folder
# functions (APIs) defined in this file follows OTLP 1.1.0
# https://opentelemetry.io/docs/specs/otlp/#otlphttp-request
# to provide OTLP/HTTP endpoint as OTEL collector

import json

from flask import request
from google.protobuf.json_format import MessageToJson
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

from promptflow._sdk._utils import parse_kv_from_pb_attribute
from promptflow._sdk.entities._trace import Span


def trace_collector():
    content_type = request.headers.get("Content-Type")
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
                "attributes": resource_attributes,
                "schema_url": resource_span.schema_url,
            }
            for scope_span in resource_span.scope_spans:
                for span in scope_span.spans:
                    # TODO: persist with batch
                    Span._from_protobuf_object(span, resource=resource)._persist()
        return "Traces received", 200

    # JSON protobuf encoding
    elif "application/json" in content_type:
        raise NotImplementedError
