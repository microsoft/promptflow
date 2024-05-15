# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path

from marshmallow import ValidationError, fields, pre_load, validate, validates_schema

from promptflow._constants import LANGUAGE_KEY, ConnectionType, FlowLanguage
from promptflow._proxy import ProxyFactory
from promptflow._sdk._constants import BASE_PATH_CONTEXT_KEY, FlowType
from promptflow._sdk.schemas._base import PatchedSchemaMeta, YamlFileSchema
from promptflow._sdk.schemas._fields import LocalPathField, NestedField
from promptflow.contracts.tool import ValueType
from promptflow.core._model_configuration import MODEL_CONFIG_NAME_2_CLASS
from promptflow.core._prompty_utils import resolve_references


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
    environment_variables = fields.Dict()

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


ALLOWED_TYPES = [
    ValueType.STRING.value,
    ValueType.INT.value,
    ValueType.DOUBLE.value,
    ValueType.BOOL.value,
    ValueType.LIST.value,
    ValueType.OBJECT.value,
]


class FlexFlowInputSchema(FlowInputSchema):
    type = fields.Str(
        required=True,
        # TODO 3062609: Flex flow GPT-V support
        validate=validate.OneOf(ALLOWED_TYPES),
    )


class FlexFlowInitSchema(FlowInputSchema):
    type = fields.Str(
        required=True,
        validate=validate.OneOf(
            ALLOWED_TYPES
            + list(
                map(lambda x: f"{x.value}Connection", filter(lambda x: x != ConnectionType._NOT_SET, ConnectionType))
            )
            + list(MODEL_CONFIG_NAME_2_CLASS.keys())
        ),
    )


class FlexFlowOutputSchema(FlowOutputSchema):
    type = fields.Str(
        required=True,
        validate=validate.OneOf(ALLOWED_TYPES),
    )


class FlexFlowSchema(BaseFlowSchema):
    """Schema for eager flow."""

    # entry point for eager flow
    entry = fields.Str(required=True)
    inputs = fields.Dict(keys=fields.Str(), values=NestedField(FlexFlowInputSchema), required=False)
    outputs = fields.Dict(keys=fields.Str(), values=NestedField(FlexFlowOutputSchema), required=False)
    init = fields.Dict(keys=fields.Str(), values=NestedField(FlexFlowInitSchema), required=False)
    sample = fields.Dict(keys=fields.Str(validate=validate.OneOf(["init", "inputs"])), required=False)
    code = LocalPathField()

    @validates_schema(skip_on_field_errors=False)
    def validate_entry(self, data, **kwargs):
        """Validate entry."""
        # the match of entry and input/output ports will be checked in entity._custom_validate instead of here
        language = data.get(LANGUAGE_KEY, FlowLanguage.Python)
        inspector_proxy = ProxyFactory().create_inspector_proxy(language=language)
        if not inspector_proxy.is_flex_flow_entry(data.get("entry", None)):
            raise ValidationError(field_name="entry", message=f"Entry function {data['entry']} is not valid.")

    @pre_load
    def resolve_sample(self, data, **kwargs):
        sample_dict = data.get("sample", {})
        if sample_dict:
            base_path = Path(self.context[BASE_PATH_CONTEXT_KEY])
            sample_dict = resolve_references(origin=sample_dict, base_path=base_path)
            data["sample"] = sample_dict
        return data


class PromptySchema(BaseFlowSchema):
    """Schema for prompty."""

    model = fields.Dict()
    inputs = fields.Dict()
