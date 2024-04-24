# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from marshmallow import RAISE, ValidationError, fields, post_load, pre_load

from promptflow._sdk._constants import ExperimentNodeType
from promptflow._sdk.schemas._base import PatchedSchemaMeta, YamlFileSchema
from promptflow._sdk.schemas._fields import (
    LocalPathField,
    NestedField,
    PrimitiveValueField,
    StringTransformedEnum,
    UnionField,
)
from promptflow._sdk.schemas._run import ManagedIdentitySchema, ResourcesSchema, RunSchema, UserIdentitySchema


class CommandNodeSchema(YamlFileSchema):
    # TODO: Not finalized now. Need to revisit.
    name = fields.Str(required=True)
    display_name = fields.Str()
    type = StringTransformedEnum(allowed_values=ExperimentNodeType.COMMAND, required=True)
    code = LocalPathField()
    command = fields.Str(required=True)
    inputs = fields.Dict(keys=fields.Str)
    outputs = fields.Dict(keys=fields.Str, values=LocalPathField(allow_none=True, check_exists=False))
    environment_variables = fields.Dict(keys=fields.Str, values=fields.Str)
    # runtime field, only available for cloud run
    runtime = fields.Str()
    # raise unknown exception for unknown fields in resources
    resources = NestedField(ResourcesSchema, unknown=RAISE)
    # raise unknown exception for unknown fields in identity
    identity = UnionField(
        [
            NestedField(ManagedIdentitySchema, unknown=RAISE),
            NestedField(UserIdentitySchema, unknown=RAISE),
        ]
    )


class FlowNodeSchema(RunSchema):
    class Meta:
        exclude = ["flow", "column_mapping", "data", "run"]

    name = fields.Str(required=True)
    type = StringTransformedEnum(allowed_values=ExperimentNodeType.FLOW, required=True)
    inputs = fields.Dict(keys=fields.Str)
    path = UnionField([LocalPathField(required=True), fields.Str(required=True)])
    init = fields.Dict(keys=fields.Str)

    @pre_load
    def warning_unknown_fields(self, data, **kwargs):
        # Override to avoid warning here
        return data


class ChatRoleSchema(YamlFileSchema):
    """Schema for chat role."""

    role = fields.Str(required=True)
    path = UnionField([LocalPathField(required=True), fields.Str(required=True)])
    inputs = fields.Dict(keys=fields.Str)


class ChatGroupSchema(YamlFileSchema):
    """Schema for chat group."""

    name = fields.Str(required=True)
    type = StringTransformedEnum(allowed_values=ExperimentNodeType.CHAT_GROUP, required=True)
    max_turns = fields.Int()
    max_tokens = fields.Int()
    max_time = fields.Int()
    stop_signal = fields.Str()
    roles = fields.List(NestedField(ChatRoleSchema))
    code = LocalPathField()  # points to a folder in which the chat group is defined

    @post_load
    def _validate_roles(self, data, **kwargs):
        from collections import Counter

        roles = data.get("roles", [])
        if not roles:
            raise ValidationError("Chat group should have at least one role.")

        # check if there is duplicate role name
        role_names = [role["role"] for role in roles]
        if len(role_names) != len(set(role_names)):
            counter = Counter(role_names)
            duplicate_roles = [role for role in counter if counter[role] > 1]
            raise ValidationError(f"Duplicate roles are not allowed: {duplicate_roles!r}.")

        return data


class ExperimentDataSchema(metaclass=PatchedSchemaMeta):
    name = fields.Str(required=True)
    path = LocalPathField(required=True)


class ExperimentInputSchema(metaclass=PatchedSchemaMeta):
    name = fields.Str(required=True)
    type = fields.Str(required=True)
    default = PrimitiveValueField()


class ExperimentTemplateSchema(YamlFileSchema):
    description = fields.Str()
    data = fields.List(NestedField(ExperimentDataSchema))  # Optional
    inputs = fields.List(NestedField(ExperimentInputSchema))  # Optional
    nodes = fields.List(
        UnionField(
            [
                NestedField(CommandNodeSchema),
                NestedField(FlowNodeSchema),
                NestedField(ChatGroupSchema),
            ]
        ),
        required=True,
    )

    @post_load
    def resolve_nodes(self, data, **kwargs):
        from promptflow._sdk.entities._experiment import ChatGroupNode, CommandNode, FlowNode

        nodes = data.get("nodes", [])
        resolved_nodes = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_type = node.get("type", None)
            if node_type == ExperimentNodeType.FLOW:
                resolved_nodes.append(FlowNode._load_from_dict(data=node, context=self.context, additional_message=""))
            elif node_type == ExperimentNodeType.COMMAND:
                resolved_nodes.append(
                    CommandNode._load_from_dict(data=node, context=self.context, additional_message="")
                )
            elif node_type == ExperimentNodeType.CHAT_GROUP:
                resolved_nodes.append(
                    ChatGroupNode._load_from_dict(data=node, context=self.context, additional_message="")
                )
            else:
                raise ValueError(f"Unknown node type {node_type} for node {node}.")
        data["nodes"] = resolved_nodes

        return data

    @post_load
    def resolve_data_and_inputs(self, data, **kwargs):
        from promptflow._sdk.entities._experiment import ExperimentData, ExperimentInput

        def resolve_resource(key, cls):
            items = data.get(key, [])
            resolved_result = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                resolved_result.append(
                    cls._load_from_dict(
                        data=item,
                        context=self.context,
                        additional_message=f"Failed to load {cls.__name__}",
                    )
                )
            return resolved_result

        data["data"] = resolve_resource("data", ExperimentData)
        data["inputs"] = resolve_resource("inputs", ExperimentInput)

        return data


class ExperimentSchema(ExperimentTemplateSchema):
    name = fields.Str()
    node_runs = fields.Dict(keys=fields.Str(), values=fields.Str())  # TODO: Revisit this
    status = fields.Str(dump_only=True)
    properties = fields.Dict(keys=fields.Str(), values=fields.Str(allow_none=True))
    created_on = fields.Str(dump_only=True)
    last_start_time = fields.Str(dump_only=True)
    last_end_time = fields.Str(dump_only=True)
