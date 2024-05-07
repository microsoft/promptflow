# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import copy

from marshmallow import ValidationError, fields, post_load, pre_dump, validates

from promptflow._constants import ConnectionType, CustomStrongTypeConnectionConfigs
from promptflow._sdk._constants import SCHEMA_KEYS_CONTEXT_CONFIG_KEY, SCHEMA_KEYS_CONTEXT_SECRET_KEY
from promptflow._sdk.schemas._base import PatchedSchemaMeta, YamlFileSchema
from promptflow._sdk.schemas._fields import StringTransformedEnum
from promptflow._utils.utils import camel_to_snake
from promptflow.constants import ConnectionAuthMode, ConnectionDefaultApiVersion


class ConnectionSchema(YamlFileSchema):
    name = fields.Str(attribute="name")
    module = fields.Str(dump_default="promptflow.connections")
    created_date = fields.Str(dump_only=True)
    last_modified_date = fields.Str(dump_only=True)
    expiry_time = fields.Str(dump_only=True)

    @pre_dump
    def _pre_dump(self, data, **kwargs):
        from promptflow._sdk.entities._connection import _Connection

        if not isinstance(data, _Connection):
            return data
        # Update the type replica of the connection object to match schema
        copied = copy.deepcopy(data)
        copied.type = camel_to_snake(copied.type)
        return copied


class AADSupportedSchemaMixin(metaclass=PatchedSchemaMeta):
    auth_mode = StringTransformedEnum(
        allowed_values=[ConnectionAuthMode.MEID_TOKEN, ConnectionAuthMode.KEY],
        allow_none=True,
        dump_default=ConnectionAuthMode.KEY,
    )

    @post_load()
    def _validate(self, data, **kwargs):
        # Validate api_key for KEY and None
        if data.get("auth_mode") != ConnectionAuthMode.MEID_TOKEN and not data.get("api_key"):
            raise ValidationError("'api_key' is required for key auth mode connection.")
        return data


class AzureOpenAIConnectionSchema(ConnectionSchema, AADSupportedSchemaMixin):
    type = StringTransformedEnum(allowed_values="azure_open_ai", required=True)
    api_key = fields.Str()
    api_base = fields.Str(required=True)
    api_type = fields.Str(dump_default="azure")
    api_version = fields.Str(dump_default=ConnectionDefaultApiVersion.AZURE_OPEN_AI)
    resource_id = fields.Str()


class OpenAIConnectionSchema(ConnectionSchema):
    type = StringTransformedEnum(allowed_values="open_ai", required=True)
    api_key = fields.Str(required=True)
    organization = fields.Str()
    base_url = fields.Str()


class ServerlessConnectionSchema(ConnectionSchema):
    type = StringTransformedEnum(allowed_values=camel_to_snake(ConnectionType.SERVERLESS), required=True)
    api_key = fields.Str(required=True)
    api_base = fields.Str(required=True)


class EmbeddingStoreConnectionSchema(ConnectionSchema):
    module = fields.Str(dump_default="promptflow_vectordb.connections")
    api_key = fields.Str(required=True)
    api_base = fields.Str(required=True)


class QdrantConnectionSchema(EmbeddingStoreConnectionSchema):
    type = StringTransformedEnum(allowed_values=camel_to_snake(ConnectionType.QDRANT), required=True)


class WeaviateConnectionSchema(EmbeddingStoreConnectionSchema):
    type = StringTransformedEnum(allowed_values=camel_to_snake(ConnectionType.WEAVIATE), required=True)


class CognitiveSearchConnectionSchema(ConnectionSchema, AADSupportedSchemaMixin):
    type = StringTransformedEnum(
        allowed_values=camel_to_snake(ConnectionType.COGNITIVE_SEARCH),
        required=True,
    )
    api_key = fields.Str()
    api_base = fields.Str(required=True)
    api_version = fields.Str(dump_default=ConnectionDefaultApiVersion.COGNITIVE_SEARCH)


class SerpConnectionSchema(ConnectionSchema):
    type = StringTransformedEnum(allowed_values=camel_to_snake(ConnectionType.SERP), required=True)
    api_key = fields.Str(required=True)


class AzureAIServicesConnectionSchema(ConnectionSchema, AADSupportedSchemaMixin):
    type = StringTransformedEnum(
        allowed_values=camel_to_snake(ConnectionType.AZURE_AI_SERVICES),
        required=True,
    )
    api_key = fields.Str()
    endpoint = fields.Str(required=True)


class AzureContentSafetyConnectionSchema(ConnectionSchema):
    type = StringTransformedEnum(
        allowed_values=camel_to_snake(ConnectionType.AZURE_CONTENT_SAFETY),
        required=True,
    )
    api_key = fields.Str(required=True)
    endpoint = fields.Str(required=True)
    api_version = fields.Str(dump_default=ConnectionDefaultApiVersion.AZURE_CONTENT_SAFETY)
    api_type = fields.Str(dump_default="Content Safety")


class FormRecognizerConnectionSchema(ConnectionSchema):
    type = StringTransformedEnum(
        allowed_values=camel_to_snake(ConnectionType.FORM_RECOGNIZER),
        required=True,
    )
    api_key = fields.Str(required=True)
    endpoint = fields.Str(required=True)
    api_version = fields.Str(dump_default=ConnectionDefaultApiVersion.FORM_RECOGNIZER)
    api_type = fields.Str(dump_default="Form Recognizer")


class CustomConnectionSchema(ConnectionSchema):
    type = StringTransformedEnum(allowed_values=camel_to_snake(ConnectionType.CUSTOM), required=True)
    configs = fields.Dict(keys=fields.Str(), values=fields.Str())
    # Secrets is a must-have field for CustomConnection
    secrets = fields.Dict(keys=fields.Str(), values=fields.Str(), required=True)


class CustomStrongTypeConnectionSchema(CustomConnectionSchema):
    name = fields.Str(attribute="name")
    module = fields.Str(required=True)
    custom_type = fields.Str(required=True)
    package = fields.Str(required=True)
    package_version = fields.Str(required=True)

    # TODO: validate configs and secrets
    @validates("configs")
    def validate_configs(self, value):
        schema_config_keys = self.context.get(SCHEMA_KEYS_CONTEXT_CONFIG_KEY, None)
        if schema_config_keys:
            for key in value:
                if CustomStrongTypeConnectionConfigs.is_custom_key(key) and key not in schema_config_keys:
                    raise ValidationError(f"Invalid config key {key}, please check the schema.")

    @validates("secrets")
    def validate_secrets(self, value):
        schema_secret_keys = self.context.get(SCHEMA_KEYS_CONTEXT_SECRET_KEY, None)
        if schema_secret_keys:
            for key in value:
                if key not in schema_secret_keys:
                    raise ValidationError(f"Invalid secret key {key}, please check the schema.")
