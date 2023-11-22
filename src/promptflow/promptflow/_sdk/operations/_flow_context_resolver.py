# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from functools import lru_cache
from os import PathLike
from pathlib import Path
from typing import Dict

from promptflow._sdk._constants import NODES
from promptflow._sdk._utils import get_local_connections_from_executable, parse_variant
from promptflow._sdk.entities import FlowContext
from promptflow._sdk.entities._flow import Flow
from promptflow._utils.flow_utils import load_flow_dag
from promptflow.contracts.flow import Flow as ExecutableFlow
from promptflow.contracts.flow import Node
from promptflow.exceptions import UserErrorException
from promptflow.executor import FlowExecutor

# Resolve flow context to executor
# Resolve flow according to flow context
#   Resolve connection, variant, overwrite, store in-memory
# create executor based on resolved flow
# cache executor if flow context not changed (define hash function for flow context).


class FlowContextResolver:
    """Flow context resolver."""

    def __init__(self, flow_path: PathLike):
        from promptflow import PFClient

        self.flow_path, self.flow_dag = load_flow_dag(flow_path=Path(flow_path))
        self.working_dir = Path(self.flow_path).parent.resolve()
        self.node_name_2_node: Dict[str, Node] = {node["name"]: node for node in self.flow_dag[NODES]}
        self.client = PFClient()

    @classmethod
    @lru_cache
    def create(cls, flow: Flow) -> FlowExecutor:
        """Create flow executor."""
        resolver = cls(flow_path=flow.path)
        resolver._resolve(flow_context=flow.context)
        return resolver._create_executor(flow_context=flow.context)

    def _resolve(self, flow_context: FlowContext):
        """Resolve flow context to executor."""
        # TODO(2813319): support node overrides
        # TODO: define priority of the contexts
        flow_context._resolve_connections()
        self._resolve_variant(flow_context=flow_context)._resolve_connections(
            flow_context=flow_context,
        )._resolve_overrides(flow_context=flow_context)

    def _resolve_variant(self, flow_context: FlowContext) -> "FlowContextResolver":
        """Resolve variant of the flow and store in-memory."""
        # TODO: put all varint string parser here
        if not flow_context.variant:
            return self
        else:
            tuning_node, variant = parse_variant(flow_context.variant)

        from promptflow._sdk._submitter import overwrite_variant

        overwrite_variant(
            flow_dag=self.flow_dag,
            tuning_node=tuning_node,
            variant=variant,
        )
        return self

    def _resolve_connections(self, flow_context: FlowContext) -> "FlowContextResolver":
        """Resolve connections of the flow and store in-memory."""
        from promptflow._sdk._submitter import overwrite_connections

        overwrite_connections(
            flow_dag=self.flow_dag,
            connections=flow_context.connections,
            working_dir=self.working_dir,
        )
        return self

    def _resolve_overrides(self, flow_context: FlowContext) -> "FlowContextResolver":
        """Resolve overrides of the flow and store in-memory."""
        from promptflow._sdk._submitter import overwrite_flow

        overwrite_flow(
            flow_dag=self.flow_dag,
            params_overrides=flow_context.overrides,
        )

        return self

    def _load_connections(self, flow_context: FlowContext, executable_flow: ExecutableFlow):
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

    def _create_executor(self, flow_context: FlowContext) -> FlowExecutor:
        executable_flow = ExecutableFlow._from_dict(flow_dag=self.flow_dag, working_dir=self.working_dir)

        connections = self._load_connections(flow_context=flow_context, executable_flow=executable_flow)

        executor = FlowExecutor._create_from_flow(
            flow=executable_flow, connections=connections, working_dir=self.working_dir, raise_ex=True
        )
        executor.enable_streaming_for_llm_flow(lambda: flow_context.streaming)

        return executor
