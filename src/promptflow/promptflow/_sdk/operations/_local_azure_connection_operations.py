# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import re
from typing import List

from promptflow._sdk._constants import AZURE_WORKSPACE_REGEX_FORMAT, MAX_LIST_CLI_RESULTS
from promptflow._sdk._telemetry import ActivityType, WorkspaceTelemetryMixin, monitor_operation
from promptflow._sdk._utils import interactive_credential_disabled, is_from_cli, is_github_codespaces, print_red_error
from promptflow._sdk.entities._connection import _Connection
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow.azure._utils.gerneral import get_arm_token

logger = get_cli_sdk_logger()


class LocalAzureConnectionOperations(WorkspaceTelemetryMixin):
    def __init__(self, connection_provider, **kwargs):
        self._subscription_id, self._resource_group, self._workspace_name = self._extract_workspace(connection_provider)
        self._credential = kwargs.pop("credential", None) or self._get_credential()
        super().__init__(
            subscription_id=self._subscription_id,
            resource_group_name=self._resource_group,
            workspace_name=self._workspace_name,
            **kwargs,
        )
        # Lazy init client as ml_client initialization require workspace read permission
        self._pfazure_client = None
        self._user_agent = kwargs.pop("user_agent", None)

    @property
    def _client(self):
        if self._pfazure_client is None:
            from promptflow.azure._pf_client import PFClient as PFAzureClient

            self._pfazure_client = PFAzureClient(
                # TODO: disable interactive credential when starting as a service
                credential=self._credential,
                subscription_id=self._subscription_id,
                resource_group_name=self._resource_group,
                workspace_name=self._workspace_name,
                user_agent=self._user_agent,
            )
        return self._pfazure_client

    @classmethod
    def _get_credential(cls):
        from azure.ai.ml._azure_environments import AzureEnvironments, EndpointURLS, _get_cloud, _get_default_cloud_name
        from azure.identity import DefaultAzureCredential, DeviceCodeCredential

        if is_from_cli():
            try:
                # Try getting token for cli without interactive login
                cloud_name = _get_default_cloud_name()
                if cloud_name != AzureEnvironments.ENV_DEFAULT:
                    cloud = _get_cloud(cloud=cloud_name)
                    authority = cloud.get(EndpointURLS.ACTIVE_DIRECTORY_ENDPOINT)
                    credential = DefaultAzureCredential(authority=authority, exclude_shared_token_cache_credential=True)
                else:
                    credential = DefaultAzureCredential()
                get_arm_token(credential=credential)
            except Exception:
                print_red_error(
                    "Please run 'az login' or 'az login --use-device-code' to set up account. "
                    "See https://docs.microsoft.com/cli/azure/authenticate-azure-cli for more details."
                )
                exit(1)
        if interactive_credential_disabled():
            return DefaultAzureCredential(exclude_interactive_browser_credential=True)
        if is_github_codespaces():
            # For code spaces, append device code credential as the fallback option.
            credential = DefaultAzureCredential()
            credential.credentials = (*credential.credentials, DeviceCodeCredential())
            return credential
        return DefaultAzureCredential(exclude_interactive_browser_credential=False)

    @classmethod
    def _extract_workspace(cls, connection_provider):
        match = re.match(AZURE_WORKSPACE_REGEX_FORMAT, connection_provider)
        if not match or len(match.groups()) != 5:
            raise ValueError(
                "Malformed connection provider string, expected azureml:/subscriptions/<subscription_id>/"
                "resourceGroups/<resource_group>/providers/Microsoft.MachineLearningServices/"
                f"workspaces/<workspace_name>, got {connection_provider}"
            )
        subscription_id = match.group(1)
        resource_group = match.group(3)
        workspace_name = match.group(5)
        return subscription_id, resource_group, workspace_name

    @monitor_operation(activity_name="pf.connections.azure.list", activity_type=ActivityType.PUBLICAPI)
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
        return self._client._connections.list()

    @monitor_operation(activity_name="pf.connections.azure.get", activity_type=ActivityType.PUBLICAPI)
    def get(self, name: str, **kwargs) -> _Connection:
        """Get a connection entity.

        :param name: Name of the connection.
        :type name: str
        :return: connection object retrieved from the database.
        :rtype: ~promptflow.sdk.entities._connection._Connection
        """
        with_secrets = kwargs.get("with_secrets", False)
        if with_secrets:
            # Do not use pfazure_client here as it requires workspace read permission
            # Get secrets from arm only requires workspace listsecrets permission
            from promptflow.azure.operations._arm_connection_operations import ArmConnectionOperations

            return ArmConnectionOperations._direct_get(
                name, self._subscription_id, self._resource_group, self._workspace_name, self._credential
            )
        return self._client._connections.get(name)

    @monitor_operation(activity_name="pf.connections.azure.delete", activity_type=ActivityType.PUBLICAPI)
    def delete(self, name: str) -> None:
        """Delete a connection entity.

        :param name: Name of the connection.
        :type name: str
        """
        raise NotImplementedError(
            "Delete workspace connection is not supported in promptflow, "
            "please manage it in workspace portal, az ml cli or AzureML SDK."
        )

    @monitor_operation(activity_name="pf.connections.azure.create_or_update", activity_type=ActivityType.PUBLICAPI)
    def create_or_update(self, connection: _Connection, **kwargs):
        """Create or update a connection.

        :param connection: Run object to create or update.
        :type connection: ~promptflow.sdk.entities._connection._Connection
        """
        raise NotImplementedError(
            "Create or update workspace connection is not supported in promptflow, "
            "please manage it in workspace portal, az ml cli or AzureML SDK."
        )
