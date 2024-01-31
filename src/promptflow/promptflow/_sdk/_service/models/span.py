# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from flask_restx import fields

from promptflow._constants import (
    SpanAttributeFieldName,
    SpanContextFieldName,
    SpanFieldName,
    SpanResourceAttributesFieldName,
    SpanResourceFieldName,
    SpanStatusFieldName,
)

context_model = {
    SpanContextFieldName.TRACE_ID: fields.String(required=True),
    SpanContextFieldName.SPAN_ID: fields.String(required=True),
    SpanContextFieldName.TRACE_STATE: fields.String(required=True),
}
status_model = {
    SpanStatusFieldName.STATUS_CODE: fields.String(required=True),
}
attributes_model = {
    SpanAttributeFieldName.FRAMEWORK: fields.String(required=True, default="promptflow"),
    SpanAttributeFieldName.SPAN_TYPE: fields.String(required=True, default="Function"),
    SpanAttributeFieldName.FUNCTION: fields.String(required=True),
    SpanAttributeFieldName.INPUTS: fields.String(required=True),
    SpanAttributeFieldName.OUTPUT: fields.String(required=True),
    SpanAttributeFieldName.SESSION_ID: fields.String(required=True),
    SpanAttributeFieldName.PATH: fields.String,
    SpanAttributeFieldName.FLOW_ID: fields.String,
    SpanAttributeFieldName.RUN: fields.String,
    SpanAttributeFieldName.EXPERIMENT: fields.String,
}
resource_attributes_model = {
    SpanResourceAttributesFieldName.SERVICE_NAME: fields.String(default="promptflow"),
}
resource_model = {
    SpanResourceFieldName.ATTRIBUTES: fields.Nested(resource_attributes_model, required=True),
    SpanResourceFieldName.SCHEMA_URL: fields.String,
}
span_model = {
    SpanFieldName.NAME: fields.String(required=True),
    SpanFieldName.CONTEXT: fields.Nested(context_model, required=True),
    SpanFieldName.KIND: fields.String(required=True),
    SpanFieldName.PARENT_ID: fields.String,
    SpanFieldName.START_TIME: fields.DateTime(dt_format="iso8601"),
    SpanFieldName.END_TIME: fields.DateTime(dt_format="iso8601"),
    SpanFieldName.STATUS: fields.Nested(status_model),
    SpanFieldName.ATTRIBUTES: fields.Nested(attributes_model, required=True),
    SpanFieldName.EVENTS: fields.List(fields.String),
    SpanFieldName.LINKS: fields.List(fields.String),
    SpanFieldName.RESOURCE: fields.Nested(resource_model, required=True),
}

models = [
    ("Context", context_model),
    ("Status", status_model),
    ("Attributes", attributes_model),
    ("ResourceAttributes", resource_attributes_model),
    ("Resource", resource_model),
    ("Span", span_model),
]
