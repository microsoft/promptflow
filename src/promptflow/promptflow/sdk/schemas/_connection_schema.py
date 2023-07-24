# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from marshmallow import fields

from promptflow.sdk._constants import ConnectionType
from promptflow.sdk._utils import snake_to_camel
from promptflow.sdk.schemas._base import YamlFileSchema
from promptflow.sdk.schemas._fields import StringTransformedEnum

type_dict = {
    "azure_open_ai": ConnectionType.AZURE_OPEN_AI,
    "open_ai": ConnectionType.OPEN_AI,
}


def casing_type(x):
    if x in type_dict:
        return type_dict.get(x)
    return snake_to_camel(x)


class ConnectionSchema(YamlFileSchema):
    name = fields.Str(attribute="name")
    module = fields.Str(dump_default="promptflow.connections")
    created_date = fields.Str(dump_only=True)
    last_modified_date = fields.Str(dump_only=True)
    expiry_time = fields.Str(dump_only=True)


class AzureOpenAIConnectionSchema(ConnectionSchema):
    type = StringTransformedEnum(
        allowed_values=ConnectionType.AZURE_OPEN_AI, casing_transform=casing_type, required=True
    )
    api_key = fields.Str(required=True)
    api_base = fields.Str(required=True)
    api_type = fields.Str(dump_default="azure")
    api_version = fields.Str(dump_default="2023-03-15-preview")


class OpenAIConnectionSchema(ConnectionSchema):
    type = StringTransformedEnum(allowed_values=ConnectionType.OPEN_AI, casing_transform=casing_type, required=True)
    api_key = fields.Str(required=True)
    organization = fields.Str()


class QdrantConnectionSchema(ConnectionSchema):
    type = StringTransformedEnum(allowed_values=ConnectionType.QDRANT, casing_transform=casing_type, required=True)
    api_key = fields.Str(required=True)
    api_base = fields.Str(required=True)


class CognitiveSearchConnectionSchema(ConnectionSchema):
    type = StringTransformedEnum(
        allowed_values=ConnectionType.COGNITIVE_SEARCH, casing_transform=casing_type, required=True
    )
    api_key = fields.Str(required=True)
    api_base = fields.Str(required=True)
    api_version = fields.Str(dump_default="2023-07-01-Preview")


class SerpConnectionSchema(ConnectionSchema):
    type = StringTransformedEnum(allowed_values=ConnectionType.SERP, casing_transform=casing_type, required=True)
    api_key = fields.Str(required=True)


class AzureContentSafetyConnectionSchema(ConnectionSchema):
    type = StringTransformedEnum(
        allowed_values=ConnectionType.AZURE_CONTENT_SAFETY, casing_transform=casing_type, required=True
    )
    api_key = fields.Str(required=True)
    endpoint = fields.Str(required=True)
    api_version = fields.Str(dump_default="2023-04-30-preview")
    api_type = fields.Str(dump_default="Content Safety")


class FormRecognizerConnectionSchema(ConnectionSchema):
    type = StringTransformedEnum(
        allowed_values=ConnectionType.FORM_RECOGNIZER, casing_transform=casing_type, required=True
    )
    api_key = fields.Str(required=True)
    endpoint = fields.Str(required=True)
    api_version = fields.Str(dump_default="2023-07-31")
    api_type = fields.Str(dump_default="Form Recognizer")


class CustomConnectionSchema(ConnectionSchema):
    type = StringTransformedEnum(allowed_values=ConnectionType.CUSTOM, casing_transform=casing_type, required=True)
    configs = fields.Dict(keys=fields.Str(), values=fields.Str())
    # Secrets is a must-have field for CustomConnection
    secrets = fields.Dict(keys=fields.Str(), values=fields.Str(), required=True)
