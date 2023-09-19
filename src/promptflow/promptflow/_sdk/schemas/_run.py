# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os.path

from dotenv import dotenv_values
from marshmallow import fields, post_load

from promptflow._sdk.schemas._base import PatchedSchemaMeta, YamlFileSchema
from promptflow._sdk.schemas._fields import LocalPathField, NestedField, UnionField


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


class ResourcesSchema(metaclass=PatchedSchemaMeta):
    """Schema for resources."""

    instance_type = fields.Str()
    idle_time_before_shutdown_minutes = fields.Int()


class RemotePathStr(fields.Str):
    default_error_messages = {
        "invalid_path": "Invalid remote path. "
        "Currently only azureml://xxx or public URL(e.g. http://xxx) are supported.",
    }

    def _validate(self, value):
        from promptflow.azure._utils.gerneral import is_remote_uri

        # inherited validations like required, allow_none, etc.
        super(RemotePathStr, self)._validate(value)

        if value is None:
            return
        if not is_remote_uri(value):
            raise self.make_error(
                "invalid_path",
            )


class RunSchema(YamlFileSchema):
    """Base schema for all run schemas."""

    # region: common fields
    name = fields.Str()
    display_name = fields.Str(required=False)
    tags = fields.Dict(keys=fields.Str(), values=fields.Str(allow_none=True))
    status = fields.Str(dump_only=True)
    description = fields.Str(attribute="description")
    properties = fields.Dict(keys=fields.Str(), values=fields.Str(allow_none=True))
    # endregion: common fields

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
    data = UnionField([LocalPathField(), RemotePathStr()])
    column_mapping = fields.Dict(keys=fields.Str)
    # runtime field, only available for cloud run
    runtime = fields.Str()
    resources = NestedField(ResourcesSchema)
    variant = fields.Str()
    run = fields.Str()

    @post_load
    def resolve_dot_env_file(self, data, **kwargs):
        return _resolve_dot_env_file(data, **kwargs)
