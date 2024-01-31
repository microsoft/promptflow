# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import re

from marshmallow import ValidationError, fields, post_load, validate, validates_schema

from promptflow._constants import LANGUAGE_KEY, FlowLanguage
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
    language = fields.Str(
        default=FlowLanguage.Python,
        validate=validate.OneOf([FlowLanguage.Python, FlowLanguage.CSharp]),
    )
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
    path = LocalPathField(required=False)
    # entry function
    entry = fields.Str(required=True)

    @validates_schema(skip_on_field_errors=False)
    def validate_entry(self, data, **kwargs):
        """Validate entry."""
        language = data.get(LANGUAGE_KEY, FlowLanguage.Python)
        entry_regex = None
        if language == FlowLanguage.CSharp:
            entry_regex = r"\((.+)\)[a-zA-Z0-9]+(\.[a-zA-Z0-9]+)+"
        elif language == FlowLanguage.Python:
            # TODO: remove this after path is removed
            if data.get("path", None) is None:
                raise ValidationError(field_name="path", message="Missing data for required field.")

        if entry_regex is not None and not re.match(entry_regex, data["entry"]):
            raise ValidationError(field_name="entry", message=f"Entry function {data['entry']} is not valid.")

    @post_load
    def infer_path(self, data: dict, **kwargs):
        """Infer path from entry."""
        # TODO: remove this after path is removed
        language = data.get(LANGUAGE_KEY, FlowLanguage.Python)
        if language == FlowLanguage.CSharp and data.get("path", None) is None:
            # for csharp, path to flow entry file will be a dll path inferred from
            # entry by default given customer won't see the dll on authoring
            m = re.match(r"\((.+)\)[a-zA-Z0-9]+(\.[a-zA-Z0-9]+)+", data["entry"])
            if m:
                data["path"] = m.group(1) + ".dll"
        return data
