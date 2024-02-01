# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import re

from marshmallow import ValidationError, fields, validate, validates_schema

from promptflow._constants import LANGUAGE_KEY, FlowLanguage
from promptflow._sdk._constants import FlowType
from promptflow._sdk.schemas._base import PatchedSchemaMeta, YamlFileSchema
from promptflow._sdk.schemas._fields import NestedField


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


class PythonEagerFlowEntry(fields.Str):
    """Entry point for eager flow. For example: pkg.module:func"""

    default_error_messages = {
        "invalid_entry": "Provided entry {entry} has incorrect format. "
        "Python eager flow only support pkg.module:func format.",
    }

    def _validate(self, value):
        super()._validate(value)
        if not re.match(r"^[a-zA-Z0-9_.]+:[a-zA-Z0-9_]+$", value):
            raise self.make_error("invalid_entry", entry=value)


class EagerFlowSchema(BaseFlowSchema):
    """Schema for eager flow."""

    # entry point for eager flow
    entry = fields.Str(required=True)

    @validates_schema(skip_on_field_errors=False)
    def validate_entry(self, data, **kwargs):
        """Validate entry."""
        language = data.get(LANGUAGE_KEY, FlowLanguage.Python)
        entry_regex = None
        if language == FlowLanguage.CSharp:
            entry_regex = r"\((.+)\)[a-zA-Z0-9]+(\.[a-zA-Z0-9]+)+"
        elif language == FlowLanguage.Python:
            entry_regex = r"^[a-zA-Z0-9_.]+:[a-zA-Z0-9_]+$"

        if entry_regex is not None and not re.match(entry_regex, data["entry"]):
            raise ValidationError(field_name="entry", message=f"Entry function {data['entry']} is not valid.")
