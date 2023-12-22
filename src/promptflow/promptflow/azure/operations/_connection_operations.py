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

from promptflow._sdk._utils import safe_parse_object_list
from promptflow._sdk.entities._connection import _Connection
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow.azure._entities._workspace_connection_spec import WorkspaceConnectionSpec
from promptflow.azure._restclient.flow_service_caller import FlowServiceCaller

logger = get_cli_sdk_logger()


class ConnectionOperations(_ScopeDependentOperations):
    """ConnectionOperations.

    You should not instantiate this class directly. Instead, you should
    create an PFClient instance that instantiates it for you and
    attaches it as an attribute.
    """

    def __init__(
        self,
        operation_scope: OperationScope,
        operation_config: OperationConfig,
        all_operations: OperationsContainer,
        credential,
        service_caller: FlowServiceCaller,
        **kwargs: Dict,
    ):
        super(ConnectionOperations, self).__init__(operation_scope, operation_config)
        self._all_operations = all_operations
        self._service_caller = service_caller
        self._credential = credential

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

        return _Connection._from_mt_rest_object(rest_conn_result)

    def get(self, name, **kwargs):
        rest_conn = self._service_caller.get_connection(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
            connection_name=name,
            **kwargs,
        )
        return _Connection._from_mt_rest_object(rest_conn)

    def delete(self, name, **kwargs):
        return self._service_caller.delete_connection(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
            connection_name=name,
            **kwargs,
        )

    def list(self, **kwargs):
        rest_connections = self._service_caller.list_connections(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
            **kwargs,
        )
        return safe_parse_object_list(
            obj_list=rest_connections,
            parser=_Connection._from_mt_rest_object,
            message_generator=lambda x: f"Failed to load connection {x.connection_name}, skipped.",
        )

    def list_connection_specs(self, **kwargs):
        results = self._service_caller.list_connection_specs(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
            **kwargs,
        )
        return [WorkspaceConnectionSpec._from_rest_object(spec) for spec in results]
