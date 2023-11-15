# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import copy
from functools import lru_cache
from os import PathLike
from pathlib import Path
from typing import Dict

import yaml
from pydash import objects

from promptflow._sdk._constants import (
    DEFAULT_ENCODING,
    DEFAULT_VAR_ID,
    INPUTS,
    NODE,
    NODE_VARIANTS,
    NODES,
    SUPPORTED_CONNECTION_FIELDS,
    USE_VARIANTS,
    VARIANTS,
    ConnectionFields,
)
from promptflow._sdk._errors import InvalidFlowError
from promptflow._sdk._utils import get_local_connections_from_executable, parse_variant
from promptflow._sdk.entities import FlowContext
from promptflow._sdk.operations._run_submitter import _load_flow_dag
from promptflow.contracts.flow import Flow as ExecutableFlow
from promptflow.contracts.flow import Node
from promptflow.exceptions import UserErrorException
from promptflow.executor import FlowExecutor

# Resolve flow context to executor
# Resolve flow according to flow context
#   Resolve connection, variant, overwrite, store in tmp file
# create executor based on resolved flow
# cache executor if flow context not changed (define hash function for flow context).


class FlowContextResolver:
    """Flow context resolver."""

    def __init__(self, flow_path: PathLike):
        from promptflow import PFClient

        self.flow_path, self.flow_dag = _load_flow_dag(flow_path=Path(flow_path))
        self.working_dir = Path(self.flow_path).parent.resolve()
        self.node_name_2_node: Dict[str, Node] = {node["name"]: node for node in self.flow_dag[NODES]}
        # TODO: support connection provider?
        self.client = PFClient()

    @classmethod
    @lru_cache
    def create(cls, flow_path: PathLike, flow_context: FlowContext) -> FlowExecutor:
        """Create flow executor."""
        resolver = cls(flow_path=flow_path)
        return resolver.resolve(flow_context=flow_context)

    def resolve(self, flow_context: FlowContext) -> FlowExecutor:
        """Resolve flow context to executor."""
        # TODO(2813319): changing node object in resolve_overrides may cause perf issue
        flow_context._resolve_connections()
        self.resolve_variant(flow_context=flow_context).resolve_connections(
            flow_context=flow_context,
        ).resolve_overrides(flow_context=flow_context)
        # TODO: define priority of the contexts
        return self.create_executor(flow_context=flow_context)

    def _dump(self, path: Path, drop_node_variants: bool = False):
        """Dump flow dag to path."""
        # TODO: always drop node variants?
        flow_dict = copy.copy(self.flow_dag)
        if drop_node_variants:
            flow_dict.pop("node_variants")
        with open(path, "w", encoding=DEFAULT_ENCODING) as f:
            yaml.safe_dump(flow_dict, f, default_flow_style=False)

    def resolve_variant(self, flow_context: FlowContext) -> "FlowContextResolver":
        """Resolve variant of the flow and store in-memory."""
        # TODO: put all varint string parser here
        if not flow_context.variant:
            return self
        else:
            tuning_node, variant = parse_variant(flow_context.variant)

        flow_dag = self.flow_dag
        if tuning_node and tuning_node not in self.node_name_2_node:
            raise InvalidFlowError(f"Node {tuning_node} not found in flow")
        if tuning_node and variant:
            try:
                flow_dag[NODE_VARIANTS][tuning_node][VARIANTS][variant]
            except KeyError as e:
                raise InvalidFlowError(f"Variant {variant} not found for node {tuning_node}") from e
        try:
            node_variants = flow_dag.pop(NODE_VARIANTS, {})
            updated_nodes = []
            for node in flow_dag.get(NODES, []):
                if not node.get(USE_VARIANTS, False):
                    updated_nodes.append(node)
                    continue
                # update variant
                node_name = node["name"]
                if node_name not in node_variants:
                    raise InvalidFlowError(f"No variant for the node {node_name}.")
                variants_cfg = node_variants[node_name]
                variant_id = variant if node_name == tuning_node else None
                if not variant_id:
                    if DEFAULT_VAR_ID not in variants_cfg:
                        raise InvalidFlowError(f"Default variant id is not specified for {node_name}.")
                    variant_id = variants_cfg[DEFAULT_VAR_ID]
                if variant_id not in variants_cfg.get(VARIANTS, {}):
                    raise InvalidFlowError(f"Cannot find the variant {variant_id} for {node_name}.")
                variant_cfg = variants_cfg[VARIANTS][variant_id][NODE]
                updated_nodes.append({"name": node_name, **variant_cfg})
            flow_dag[NODES] = updated_nodes
        except KeyError as e:
            raise InvalidFlowError("Failed to overwrite tuning node with variant") from e
        return self

    def resolve_connections(self, flow_context: FlowContext) -> "FlowContextResolver":
        """Resolve connections of the flow and store in-memory."""
        if not flow_context.connections:
            return self
        connections = flow_context.connections
        flow_dag = self.flow_dag
        if not isinstance(connections, dict):
            raise InvalidFlowError(f"Invalid connections overwrite format: {connections}, only list is supported.")

        # Load executable flow to check if connection is LLM connection
        executable_flow = ExecutableFlow._from_dict(flow_dag=self.flow_dag, working_dir=self.working_dir)

        node_name_2_node = {node["name"]: node for node in flow_dag[NODES]}

        for node_name, connection_dict in connections.items():
            if node_name not in node_name_2_node:
                raise InvalidFlowError(f"Node {node_name} not found in flow")
            if not isinstance(connection_dict, dict):
                raise InvalidFlowError(
                    f"Invalid connection overwrite format: {connection_dict}, only dict is supported."
                )
            node = node_name_2_node[node_name]
            executable_node = executable_flow.get_node(node_name=node_name)
            if executable_flow.is_llm_node(executable_node):
                unsupported_keys = connection_dict.keys() - SUPPORTED_CONNECTION_FIELDS
                if unsupported_keys:
                    raise InvalidFlowError(
                        f"Unsupported llm connection overwrite keys: {unsupported_keys},"
                        f" only {SUPPORTED_CONNECTION_FIELDS} are supported."
                    )
                try:
                    connection = connection_dict.get(ConnectionFields.CONNECTION)
                    if connection:
                        node[ConnectionFields.CONNECTION] = connection
                    deploy_name = connection_dict.get(ConnectionFields.DEPLOYMENT_NAME)
                    if deploy_name:
                        node[INPUTS][ConnectionFields.DEPLOYMENT_NAME] = deploy_name
                except KeyError as e:
                    raise InvalidFlowError(
                        f"Failed to overwrite llm node {node_name} with connections {connections}"
                    ) from e
            else:
                connection_inputs = executable_flow.get_connection_input_names_for_node(node_name=node_name)
                for c, v in connection_dict.items():
                    if c not in connection_inputs:
                        raise InvalidFlowError(f"Connection with name {c} not found in node {node_name}'s inputs")
                    node[INPUTS][c] = v
        return self

    def resolve_overrides(self, flow_context: FlowContext):
        """Resolve overrides of the flow and store in-memory."""
        if not flow_context.overrides:
            return self

        flow_dag = self.flow_dag
        # update flow dag & change nodes list to name: obj dict
        flow_dag[NODES] = {node["name"]: node for node in flow_dag[NODES]}
        # apply overrides on flow dag
        for param, val in flow_context.overrides.items():
            objects.set_(flow_dag, param, val)
        # revert nodes to list
        flow_dag[NODES] = list(flow_dag[NODES].values())

        return self

    def load_connections(self, flow_context: FlowContext, executable_flow: ExecutableFlow):
        # validate connection objs
        connection_obj_dict = {}
        for key, connection_obj in flow_context._connection_objs.items():
            scrubbed_secrets = connection_obj._get_scrubbed_secrets()
            if scrubbed_secrets:
                raise UserErrorException(
                    f"Connection {connection_obj} contains scrubbed secrets with key {scrubbed_secrets.keys()}, "
                    "please make sure connection has decrypted secrets to use in flow execution. "
                )
            connection_obj_dict[key] = connection_obj._to_execution_connection_dict()
        connections = get_local_connections_from_executable(
            executable=executable_flow,
            client=self.client,
            connections_to_ignore=flow_context._connection_objs.keys(),
        )
        # update connections with connection objs
        connections.update(connection_obj_dict)
        return connections

    def create_executor(self, flow_context: FlowContext) -> FlowExecutor:
        # TODO: validate if it's still a valid flow
        executable_flow = ExecutableFlow.deserialize(self.flow_dag)
        executable_flow._set_tool_loader(self.working_dir)

        # Generate a flow, the code path points to the original flow folder,
        # the dag path points to the temp dag file after overwriting variant.
        connections = self.load_connections(flow_context=flow_context, executable_flow=executable_flow)
        executor = FlowExecutor._create_from_flow(
            flow=executable_flow, connections=connections, working_dir=self.working_dir, raise_ex=True
        )
        executor.enable_streaming_for_llm_flow(lambda: flow_context.streaming)
        return executor
