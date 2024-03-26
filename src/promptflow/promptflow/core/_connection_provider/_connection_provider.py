# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from abc import ABC, abstractmethod
from typing import Any

from promptflow._constants import ConnectionProviderConfig
from promptflow.core._connection_provider._utils import extract_workspace


class ConnectionProvider(ABC):
    @abstractmethod
    def get(self, name: str) -> Any:
        """Get connection by name."""
        raise NotImplementedError

    @classmethod
    def init_from_provider_config(cls, provider_config: str, credential=None):
        """Initialize the connection provider from a provider config.

        Expected value:
        - local
        - azureml://subscriptions/<your-subscription>/resourceGroups/<your-resourcegroup>/
            providers/Microsoft.MachineLearningServices/workspaces/<your-workspace>
        """
        from promptflow.core._connection_provider._local_connection_provider import LocalConnectionProvider
        from promptflow.core._connection_provider._workspace_connection_provider import WorkspaceConnectionProvider

        if not provider_config or provider_config == ConnectionProviderConfig.LOCAL:
            return LocalConnectionProvider()
        if provider_config.startswith(ConnectionProviderConfig.AZUREML):
            subscription_id, resource_group, workspace_name = extract_workspace(provider_config)
            return WorkspaceConnectionProvider(subscription_id, resource_group, workspace_name, credential)

    @classmethod
    def _init_from_env(cls):
        """Initialize the connection provider from environment variables."""
        pass
