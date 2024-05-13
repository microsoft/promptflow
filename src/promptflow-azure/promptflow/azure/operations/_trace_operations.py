# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Dict, Optional

from azure.ai.ml._scope_dependent_operations import OperationConfig, OperationScope, _ScopeDependentOperations

from promptflow._sdk._telemetry import ActivityType, WorkspaceTelemetryMixin, monitor_operation
from promptflow.azure._entities._trace import CosmosMetadata
from promptflow.azure._restclient.flow.models import TraceDbSetupRequest
from promptflow.azure._restclient.flow_service_caller import FlowServiceCaller


class TraceOperations(WorkspaceTelemetryMixin, _ScopeDependentOperations):
    """TraceOperations that can manage traces related entities."""

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

    @monitor_operation(activity_name="pfazure.traces._init_cosmos_db", activity_type=ActivityType.INTERNALCALL)
    def _init_cosmos_db(self) -> Optional[Dict]:
        # this API is deprecated and will be removed in the future
        resp = self._service_caller.init_workspace_cosmos(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
        )
        # PFS API /TraceSessions/initialize is an async API; in normal cases
        # there are two status codes: 200 and 202
        # the corresponding responses are `TraceCosmosResourceDtos` or None
        # apply `as_dict()` for the first case to make it a dict
        return resp if resp is None else resp.as_dict()

    @monitor_operation(activity_name="pfazure.traces._get_cosmos_db_token", activity_type=ActivityType.INTERNALCALL)
    def _get_cosmos_db_token(self, container_name: str, acquire_write: bool = False) -> str:
        return self._service_caller.get_cosmos_resource_token(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
            container_name=container_name,
            acquire_write=acquire_write,
        )

    @monitor_operation(activity_name="pfazure.traces._setup_cosmos_db", activity_type=ActivityType.INTERNALCALL)
    def _setup_cosmos_db(self, resource_type: str) -> None:
        body = TraceDbSetupRequest(resource_type=resource_type)
        self._service_caller.setup_workspace_cosmos(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
            body=body,
        )
        return

    def _get_cosmos_metadata(self) -> CosmosMetadata:
        rest_obj = self._service_caller.get_workspace_cosmos_metadata(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
        )
        return CosmosMetadata._from_rest_object(rest_obj)
