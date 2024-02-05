# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Dict

from azure.ai.ml._scope_dependent_operations import OperationConfig, OperationScope, _ScopeDependentOperations

from promptflow._sdk._telemetry import WorkspaceTelemetryMixin
from promptflow.azure._restclient.flow_service_caller import FlowServiceCaller


class TraceOperations(WorkspaceTelemetryMixin, _ScopeDependentOperations):
    """"""

    def __init__(
        self,
        operation_scope: OperationScope,
        operation_config: OperationConfig,
        service_caller: FlowServiceCaller,
        **kwargs: Dict,
    ):
        super().__init__(
            operation_scope=operation_scope,
            operation_config=operation_config,
            workspace_name=operation_scope.workspace_name,
            subscription_id=operation_scope.subscription_id,
            resource_group_name=operation_scope.resource_group_name,
        )
        self._service_caller = service_caller

    def _get_cosmos_db_token(self, container_name: str, acquire_write: bool = False) -> str:
        return self._service_caller.get_cosmos_resource_token(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
            container_name=container_name,
            acquire_write=acquire_write,
        )
