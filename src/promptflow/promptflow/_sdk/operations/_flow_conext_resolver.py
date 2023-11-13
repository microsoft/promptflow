# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from functools import lru_cache
from os import PathLike
from pathlib import Path

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
from promptflow._sdk._utils import parse_variant
from promptflow._sdk.entities import FlowContext
from promptflow._sdk.operations._run_submitter import _load_flow_dag
from promptflow.contracts.flow import Flow as ExecutableFlow
from promptflow.executor import FlowExecutor

# Resolve flow context to executor
# Resolve flow according to flow context
#   Resolve connection, variant, overwrite, store in tmp file
# create executor based on resolved flow
# cache executor if flow context not changed (define hash function for flow context).


class FlowContextResolver:
    """Flow context resolver."""

    def __init__(self, flow_path: PathLike, flow_context: FlowContext, working_dir: PathLike = None):
        self.flow_context = flow_context
        self.flow_path, self.flow_dag = _load_flow_dag(flow_path=Path(flow_path))
        self.node_name_2_node = {node["name"]: node for node in self.flow_dag[NODES]}
        # TODO: directly load flow_path to ExecutableFlow object
        self.executable_flow = ExecutableFlow.from_yaml(flow_file=Path(flow_path), working_dir=working_dir)

    # TODO: enable cache, add hash function for flow context
    @lru_cache()
    @classmethod
    def resolve(cls, flow_path: Path, flow_context: FlowContext) -> FlowExecutor:
        """Resolve flow context to executor."""
        resolver = cls(flow_path=flow_path, flow_context=flow_context)
        resolver.resolve_variant().resolve_connections().resolve_overrides()
        # TODO: resolve environment variables, need to recover after execution
        return resolver.create_executor()

    def _dump(self, path: Path):
        """Dump flow dag to path."""
        # TODO: use utils to avoid reference in dag.yaml
        with open(path, "w", encoding=DEFAULT_ENCODING) as f:
            yaml.safe_dump(self.flow_dag, f)

    def resolve_variant(self, drop_node_variants: bool = False) -> "FlowContextResolver":
        """Resolve variant of the flow and store in-memory."""
        # TODO: put all varint string parser here
        if not self.flow_context.variant:
            return self
        else:
            tuning_node, variant = parse_variant(self.flow_context.variant)

        if tuning_node and tuning_node not in self.node_name_2_node:
            raise InvalidFlowError(f"Node {tuning_node} not found in flow")
        if tuning_node and variant:
            try:
                self.flow_dag[NODE_VARIANTS][tuning_node][VARIANTS][variant]
            except KeyError as e:
                raise InvalidFlowError(f"Variant {variant} not found for node {tuning_node}") from e
        try:
            node_variants = (
                self.flow_dag.pop(NODE_VARIANTS, {}) if drop_node_variants else self.flow_dag.get(NODE_VARIANTS, {})
            )
            updated_nodes = []
            for node in self.flow_dag.get(NODES, []):
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
            self.flow_dag[NODES] = updated_nodes
        except KeyError as e:
            raise InvalidFlowError("Failed to overwrite tuning node with variant") from e
        return self

    def resolve_connections(self) -> "FlowContextResolver":
        """Resolve connections of the flow and store in-memory."""
        if not self.flow_context.connections:
            return self
        connections = self.flow_context.connections
        if not isinstance(connections, dict):
            raise InvalidFlowError(f"Invalid connections overwrite format: {connections}, only list is supported.")

        for node_name, connection_dict in connections.items():
            if node_name not in self.node_name_2_node:
                raise InvalidFlowError(f"Node {node_name} not found in flow")
            if not isinstance(connection_dict, dict):
                raise InvalidFlowError(
                    f"Invalid connection overwrite format: {connection_dict}, only dict is supported."
                )
            node = self.node_name_2_node[node_name]
            executable_node = self.executable_flow.get_node(node_name=node_name)
            if self.executable_flow.is_llm_node(executable_node):
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
                    raise KeyError(f"Failed to overwrite llm node {node_name} with connections {connections}") from e
            else:
                connection_inputs = self.executable_flow.get_connection_input_names_for_node(node_name=node_name)
                for c, v in connection_dict.items():
                    if c not in connection_inputs:
                        raise InvalidFlowError(f"Connection with name {c} not found in node {node_name}'s inputs")
                    node[INPUTS][c] = v
        return self

    def resolve_overrides(self):
        """Resolve overrides of the flow and store in-memory."""
        if not self.flow_context.overrides:
            return self
        # update flow dag & change nodes list to name: obj dict
        self.flow_dag[NODES] = {node["name"]: node for node in self.flow_dag[NODES]}
        # apply overrides on flow dag
        for param, val in self.flow_context.overrides.items():
            objects.set_(self.flow_dag, param, val)
        # revert nodes to list
        self.flow_dag[NODES] = list(self.flow_dag[NODES].values())
        return self
