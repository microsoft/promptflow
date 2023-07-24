import os
from typing import Any, Dict, List, Mapping, Optional

from promptflow.contracts.flow import Flow, Node
from promptflow.contracts.tool import Tool
from promptflow.core.connection_manager import ConnectionManager
from promptflow.executor.error_codes import NodeOfVariantNotFound, ToolOfVariantNotFound
from promptflow.executor.flow_validator import FlowValidator


class FlowRequestValidator:
    @classmethod
    def _resolve_connections(cls, connections: dict) -> dict:
        connections = {k: v for k, v in connections.items()} if connections else {}
        connections_in_env = cls._get_connections_in_env()
        connections.update(connections_in_env)  # For local test
        return connections

    @classmethod
    def ensure_flow_valid(cls, flow: Flow, connections: dict) -> Flow:
        connections = cls._resolve_connections(connections)
        return FlowValidator.ensure_flow_valid(flow, connections)

    @classmethod
    def ensure_batch_inputs_type(
        cls,
        flow: Flow,
        batch_inputs: List[Dict[str, Any]],
    ) -> List[Mapping[str, Any]]:
        return [FlowValidator.ensure_flow_inputs_type(flow, inputs, idx) for idx, inputs in enumerate(batch_inputs)]

    @classmethod
    def ensure_variants_valid(
        cls,
        variants: Optional[Mapping[str, List[Node]]],
        variants_tools: Optional[List[Tool]],
        flow: Flow,
        connections,
    ) -> Mapping[str, List[Node]]:
        if not variants:
            return {}
        connections = cls._resolve_connections(connections)
        tools_mapping = {tool.name: tool for tool in flow.tools}
        if variants_tools:
            tools_mapping.update({tool.name: tool for tool in variants_tools})
        node_names = set(node.name for node in flow.nodes)
        updated_variants = {}
        for variant_id, nodes in variants.items():
            for node in nodes:
                if node.name not in node_names:
                    msg = f"Node '{node.name}' of variant '{variant_id}' is not in the flow."
                    raise NodeOfVariantNotFound(message=msg)
                if node.tool not in tools_mapping:
                    msg = (
                        f"Node '{node.name}' of variant '{variant_id}' references tool '{node.tool}' "
                        "which is not provided."
                    )
                    raise ToolOfVariantNotFound(message=msg)
            updated_variants[variant_id] = [
                FlowValidator.ensure_node_inputs_type(tools_mapping[node.tool], node, connections) for node in nodes
            ]
        return updated_variants

    @staticmethod
    def _get_connections_in_env() -> dict:
        if "PROMPTFLOW_CONNECTIONS" in os.environ:
            return ConnectionManager.init_from_env().to_connections_dict()

        return dict()
