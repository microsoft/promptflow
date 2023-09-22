# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging
import re
from typing import List

from promptflow._sdk._constants import AZURE_WORKSPACE_REGEX_FORMAT, LOGGER_NAME, MAX_LIST_CLI_RESULTS
from promptflow._sdk._logger_factory import LoggerFactory
from promptflow._sdk.entities._connection import _Connection

logger = LoggerFactory.get_logger(name=LOGGER_NAME, verbosity=logging.WARNING)


class LocalAzureConnectionOperations:
    def __init__(self, connection_provider):
        from promptflow.azure._pf_client import PFClient as PFAzureClient

        self._connection_provider = connection_provider

        subscription_id, resource_group, workspace_name = self._extract_workspace()
        self._pfazure_client = PFAzureClient(
            credential=self._get_cred(),
            subscription_id=subscription_id,
            resource_group_name=resource_group,
            workspace_name=workspace_name,
        )

    @classmethod
    def _get_cred(cls):
        """get credential for azure storage"""
        from azure.identity import AzureCliCredential, DefaultAzureCredential

        try:
            credential = AzureCliCredential()
            credential.get_token("https://management.azure.com/.default")
        except Exception:
            credential = DefaultAzureCredential()

        return credential

    def _extract_workspace(self):
        match = re.match(AZURE_WORKSPACE_REGEX_FORMAT, self._connection_provider)
        if not match:
            raise ValueError(
                "Malformed connection provider string, expected azureml:/subscriptions/<subscription_id>/"
                "resourceGroups/<resource_group>/providers/Microsoft.MachineLearningServices/"
                f"workspaces/<workspace_name>, got {self._connection_provider}"
            )
        subscription_id = match.group(1)
        resource_group = match.group(3)
        workspace_name = match.group(4)
        return subscription_id, resource_group, workspace_name

    def list(
        self,
        max_results: int = MAX_LIST_CLI_RESULTS,
        all_results: bool = False,
    ) -> List[_Connection]:
        """List connections.

        :return: List of run objects.
        :rtype: List[~promptflow.sdk.entities._connection._Connection]
        """
        if max_results != MAX_LIST_CLI_RESULTS or all_results:
            logger.warning(
                "max_results and all_results are not supported for workspace connection and will be ignored."
            )
        return self._pfazure_client._connections.list()

    def get(self, name: str, **kwargs) -> _Connection:
        """Get a connection entity.

        :param name: Name of the connection.
        :type name: str
        :return: connection object retrieved from the database.
        :rtype: ~promptflow.sdk.entities._connection._Connection
        """
        with_secrets = kwargs.get("with_secrets", False)
        if with_secrets:
            return self._pfazure_client._arm_connections.get(name)
        return self._pfazure_client._connections.get(name)

    def delete(self, name: str) -> None:
        """Delete a connection entity.

        :param name: Name of the connection.
        :type name: str
        """
        raise NotImplementedError(
            "Delete workspace connection is not supported in promptflow, "
            "please manage it in workspace portal, az ml cli or AzureML SDK."
        )

    def create_or_update(self, connection: _Connection, **kwargs):
        """Create or update a connection.

        :param connection: Run object to create or update.
        :type connection: ~promptflow.sdk.entities._connection._Connection
        """
        raise NotImplementedError(
            "Create or update workspace connection is not supported in promptflow, "
            "please manage it in workspace portal, az ml cli or AzureML SDK."
        )
