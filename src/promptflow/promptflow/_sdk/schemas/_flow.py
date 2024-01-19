# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from marshmallow import fields, validate

from promptflow._sdk._constants import FlowType
from promptflow._sdk.schemas._base import PatchedSchemaMeta, YamlFileSchema
from promptflow._sdk.schemas._fields import LocalPathField, NestedField


class FlowInputSchema(metaclass=PatchedSchemaMeta):
    """Schema for flow input."""

    type = fields.Str(required=True)
    description = fields.Str()
    # Note: default attribute default can be various types, so we use Raw type here,
    # but when transforming to json schema, there is no equivalent type, it will become string type
    # may need to delete the default type in the generated json schema to avoid false alarm
    default = fields.Raw()
    is_chat_input = fields.Bool()
    is_chat_history = fields.Bool()


class FlowOutputSchema(metaclass=PatchedSchemaMeta):
    """Schema for flow output."""

    type = fields.Str(required=True)
    reference = fields.Str()
    description = fields.Str()
    is_chat_output = fields.Bool()


class BaseFlowSchema(YamlFileSchema):
    """Base schema for flow."""

    additional_includes = fields.List(fields.Str())
    environment = fields.Dict()

    # metadata
    type = fields.Str(validate=validate.OneOf(FlowType.get_all_values()))
    language = fields.Str()
    description = fields.Str()
    display_name = fields.Str()
    tags = fields.Dict(keys=fields.Str(), values=fields.Str())


class FlowSchema(BaseFlowSchema):
    """Schema for flow dag."""

    inputs = fields.Dict(keys=fields.Str(), values=NestedField(FlowInputSchema))
    outputs = fields.Dict(keys=fields.Str(), values=NestedField(FlowOutputSchema))
    nodes = fields.List(fields.Dict())
    node_variants = fields.Dict(keys=fields.Str(), values=fields.Dict())


class EagerFlowSchema(BaseFlowSchema):
    """Schema for eager flow."""

    # path to flow entry file.
    path = LocalPathField(required=True)
    # entry function
    entry = fields.Str(required=True)
