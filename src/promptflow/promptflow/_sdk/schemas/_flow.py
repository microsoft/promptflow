# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from marshmallow import fields, validate

from promptflow._sdk._constants import FlowType
from promptflow._sdk.schemas._base import PatchedSchemaMeta, YamlFileSchema
from promptflow._sdk.schemas._fields import NestedField
from promptflow.contracts.tool import ToolType


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


class ToolTypeSchema(metaclass=PatchedSchemaMeta):
    """Schema for ToolType."""

    type = fields.Str(validate=validate.OneOf([e.value for e in ToolType]))


class NodeSchema(metaclass=PatchedSchemaMeta):
    """Schema for flow node."""

    name = fields.Str(required=True)
    tool = fields.Str(required=True)
    inputs = fields.Dict()
    comment = fields.Str()
    api = fields.Str()
    provider = fields.Str()
    module = fields.Str()
    connection = fields.Str()
    aggregation = fields.Bool()
    enable_cache = fields.Bool()
    use_variants = fields.Bool()
    source = fields.Dict()
    type = NestedField(ToolTypeSchema)
    activate = fields.Dict()


class FlowSchema(YamlFileSchema):
    """Schema for flow dag."""

    additional_includes = fields.List(fields.Str())
    inputs = fields.Dict(keys=fields.Str(), values=NestedField(FlowInputSchema))
    outputs = fields.Dict(keys=fields.Str(), values=NestedField(FlowOutputSchema))
    nodes = fields.List(NestedField(NodeSchema))
    node_variants = fields.Dict(keys=fields.Str(), values=fields.Dict())
    environment = fields.Dict()

    # metadata
    type = fields.Str(validate=validate.OneOf(FlowType.get_all_values()))
    language = fields.Str()
    description = fields.Str()
    display_name = fields.Str()
    tags = fields.Dict(keys=fields.Str(), values=fields.Str())
