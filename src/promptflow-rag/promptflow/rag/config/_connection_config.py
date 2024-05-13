# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from promptflow.rag.constants._common import CONNECTION_ID_TEMPLATE


class ConnectionConfig:
    """Config class for connection.

    :param subscription: The subscription of a connection.
    :type subscription: str
    :param resource_group: The resource group of a connection.
    :type resource_group: str
    :param workspace: The workspace of a connection.
    :type workspace: str
    :param connection_name: The connection name.
    :type connection_name: str
    """

    def __init__(
        self,
        *,
        subscription_id: str,
        resource_group_name: str,
        workspace_name: str,
        connection_name: str,
    ) -> None:
        self.subscription_id = subscription_id
        self.resource_group_name = resource_group_name
        self.workspace_name = workspace_name
        self.connection_name = connection_name

    def build_connection_id(self) -> str:
        """Construct connection id from connection config"""

        return CONNECTION_ID_TEMPLATE.format(
            self.subscription_id,
            self.resource_group_name,
            self.workspace_name,
            self.connection_name
        )
