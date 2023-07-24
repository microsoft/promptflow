# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os.path

from dotenv import dotenv_values
from marshmallow import fields, post_load

from promptflow.sdk.schemas._base import PatchedSchemaMeta, YamlFileSchema
from promptflow.sdk.schemas._fields import LocalPathField, NestedField, UnionField


def _resolve_dot_env_file(data, **kwargs):
    """Resolve .env file to environment variables."""
    env_var = data.get("environment_variables", None)
    try:
        if env_var and os.path.exists(env_var):
            env_dict = dotenv_values(env_var)
            data["environment_variables"] = env_dict
    except TypeError:
        pass
    return data


class ConnectionOverrideSchema(metaclass=PatchedSchemaMeta):
    """Schema for connection override."""

    connection = fields.Str()
    deployment_name = fields.Str()


class ResourcesSchema(metaclass=PatchedSchemaMeta):
    """Schema for resources."""

    instance_type = fields.Str()
    idle_time_before_shutdown_minutes = fields.Int()


class RunSchema(YamlFileSchema):
    """Base schema for all run schemas."""

    name = fields.Str()
    flow = LocalPathField(required=True)
    environment_variables = UnionField(
        [
            fields.Dict(keys=fields.Str(), values=fields.Str()),
            # support load environment variables from .env file
            LocalPathField(),
        ]
    )
    connections = fields.Dict(keys=fields.Str(), values=fields.Dict(keys=fields.Str()))
    # inputs field
    data = LocalPathField()
    column_mapping = fields.Dict(keys=fields.Str)
    # runtime field, only available for cloud run
    runtime = fields.Str()
    resources = NestedField(ResourcesSchema)
    variant = fields.Str()
    run = fields.Str()

    @post_load
    def resolve_dot_env_file(self, data, **kwargs):
        return _resolve_dot_env_file(data, **kwargs)
