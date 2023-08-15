# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from typing import Dict

from azure.ai.ml._scope_dependent_operations import (
    OperationConfig,
    OperationsContainer,
    OperationScope,
    _ScopeDependentOperations,
)
from azure.ai.ml.constants._common import AzureMLResourceType
from azure.ai.ml.operations import WorkspaceOperations

from promptflow.azure._restclient.flow_service_caller import FlowServiceCaller
from promptflow._sdk.entities._connection import _Connection
from promptflow.azure._entities._workspace_connection_spec import WorkspaceConnectionSpec


class ConnectionOperations(_ScopeDependentOperations):
    """FlowOperations.

    You should not instantiate this class directly. Instead, you should
    create an MLClient instance that instantiates it for you and
    attaches it as an attribute.
    """

    def __init__(
            self,
            operation_scope: OperationScope,
            operation_config: OperationConfig,
            all_operations: OperationsContainer,
            credential,
            **kwargs: Dict,
    ):
        super(ConnectionOperations, self).__init__(operation_scope, operation_config)
        self._all_operations = all_operations
        workspace = self._workspace_operations.get(name=operation_scope.workspace_name)
        # TODO: we should only have one service caller for all operations
        self._service_caller = FlowServiceCaller(workspace, credential, **kwargs)
        self._credential = credential

    @property
    def _workspace_operations(self) -> WorkspaceOperations:
        return self._all_operations.get_operation(
            AzureMLResourceType.WORKSPACE, lambda x: isinstance(x, WorkspaceOperations)
        )

    def create_or_update(self, connection, **kwargs):
        rest_conn = connection._to_rest_object()

        # create flow draft
        rest_conn_result = self._service_caller.create_connection(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
            connection_name=connection.name,
            body=rest_conn,
        )

        return _Connection._from_rest_object(rest_conn_result)

    def get(self, name, **kwargs):
        rest_conn = self._service_caller.get_connection(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
            connection_name=name,
            **kwargs
        )

        return _Connection._from_rest_object(rest_conn)

    def delete(self, name, **kwargs):
        return self._service_caller.delete_connection(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
            connection_name=name,
            **kwargs
        )

    def list(self, **kwargs):
        rest_connections = self._service_caller.list_connections(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
            **kwargs
        )

        return [Connection._from_rest_object(conn) for conn in rest_connections]

    def list_connection_specs(
        self,
        **kwargs
    ):
        results = self._service_caller.list_connection_specs(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
            **kwargs
        )
        return [WorkspaceConnectionSpec._from_rest_object(spec) for spec in results]
