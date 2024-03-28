# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from dataclasses import asdict, dataclass

from promptflow.azure._restclient.flow.models import ConnectionConfigSpec as RestConnectionConfigSpec
from promptflow.azure._restclient.flow.models import WorkspaceConnectionSpec as RestWorkspaceConnectionSpec


@dataclass
class ConnectionConfigSpec:
    name: str
    display_name: str
    config_value_type: str
    default_value: str = None
    description: str = None
    enum_values: list = None
    is_optional: bool = False

    @classmethod
    def _from_rest_object(cls, rest_obj: RestConnectionConfigSpec):
        return cls(
            name=rest_obj.name,
            display_name=rest_obj.display_name,
            config_value_type=rest_obj.config_value_type,
            default_value=rest_obj.default_value,
            description=rest_obj.description,
            enum_values=rest_obj.enum_values,
            is_optional=rest_obj.is_optional,
        )

    def _to_dict(self):
        return asdict(self, dict_factory=lambda x: {k: v for (k, v) in x if v is not None})


@dataclass
class WorkspaceConnectionSpec:
    module: str
    connection_type: str  # Connection type example: AzureOpenAI
    flow_value_type: str  # Flow value type is the input.type on node, example: AzureOpenAIConnection
    config_specs: list = None

    @classmethod
    def _from_rest_object(cls, rest_obj: RestWorkspaceConnectionSpec):
        return cls(
            config_specs=[
                ConnectionConfigSpec._from_rest_object(config_spec) for config_spec in (rest_obj.config_specs or [])
            ],
            module=rest_obj.module,
            connection_type=rest_obj.connection_type,
            flow_value_type=rest_obj.flow_value_type,
        )

    def _to_dict(self):
        return asdict(self, dict_factory=lambda x: {k: v for (k, v) in x if v is not None})
