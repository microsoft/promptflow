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
        subscription: str,
        resource_group: str,
        workspace: str,
        connection_name: str,
    ) -> None:
        self.subscription = subscription
        self.resource_group = resource_group
        self.workspace = workspace
        self.connection_name = connection_name

    def build_connection_id(self) -> str:
        """Construct connection id from connection config"""

        return CONNECTION_ID_TEMPLATE.format(
            self.subscription,
            self.resource_group,
            self.workspace,
            self.connection_name
        )
