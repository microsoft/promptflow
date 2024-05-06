# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import os
import re
from typing import Any, Tuple

from promptflow._constants import AML_WORKSPACE_TEMPLATE
from promptflow._utils.retry_utils import retry
from promptflow.contracts.flow import Flow
from promptflow.core._serving._errors import InvalidConnectionData, MissingConnectionProvider
from promptflow.core._serving.extension.default_extension import AppExtension
from promptflow.core._serving.extension.extension_type import ExtensionType
from promptflow.core._serving.monitor.data_collector import FlowDataCollector
from promptflow.core._serving.utils import decode_dict, get_pf_serving_env, normalize_connection_name
from promptflow.core._version import __version__

USER_AGENT = f"promptflow-cloud-serving/{__version__}"
AML_DEPLOYMENT_RESOURCE_ID_REGEX = "/subscriptions/(.*)/resourceGroups/(.*)/providers/Microsoft.MachineLearningServices/workspaces/(.*)/onlineEndpoints/(.*)/deployments/(.*)"  # noqa: E501


class AzureMLExtension(AppExtension):
    """AzureMLExtension is used to create extension for azureml serving."""

    def __init__(self, logger, **kwargs):
        super().__init__(
            logger=logger, extension_type=ExtensionType.AZUREML, collector=FlowDataCollector(logger), **kwargs
        )  # noqa: E501
        # parse promptflow project path
        project_path: str = get_pf_serving_env("PROMPTFLOW_PROJECT_PATH")
        if not project_path:
            model_dir = os.getenv("AZUREML_MODEL_DIR", ".")
            model_rootdir = os.listdir(model_dir)[0]
            self.model_name = model_rootdir
            project_path = os.path.join(model_dir, model_rootdir)
        self.model_root_path = project_path
        # mlflow support in base extension
        self.project_path = self._get_mlflow_project_path(project_path)
        # initialize connections or connection provider
        # TODO: to be deprecated, remove in next major version
        self.connections = self._get_env_connections_if_exist()
        self.endpoint_name: str = None
        self.deployment_name: str = None
        self.connection_provider = None
        self.credential = _get_managed_identity_credential_with_retry()
        if len(self.connections) == 0:
            self._initialize_connection_provider()
        # initialize metrics common dimensions if exist
        self.common_dimensions = {}
        if self.endpoint_name:
            self.common_dimensions["endpoint"] = self.endpoint_name
        if self.deployment_name:
            self.common_dimensions["deployment"] = self.deployment_name
        env_dimensions = self._get_common_dimensions_from_env()
        self.common_dimensions.update(env_dimensions)

    def get_flow_project_path(self) -> str:
        return self.project_path

    def get_flow_name(self) -> str:
        return os.path.basename(self.model_root_path)

    def get_connection_provider(self) -> str:
        return self.connection_provider

    def get_blueprints(self, flow_monitor):
        return self._get_default_blueprints(flow_monitor)

    def get_override_connections(self, flow: Flow) -> Tuple[dict, dict]:
        connection_names = flow.get_connection_names()
        connections = {}
        connections_name_overrides = {}
        for connection_name in connection_names:
            # replace " " with "_" in connection name
            normalized_name = normalize_connection_name(connection_name)
            if normalized_name in os.environ:
                override_conn = os.environ[normalized_name]
                data_override = False
                # try load connection as a json
                try:
                    # data override
                    conn_data = json.loads(override_conn)
                    data_override = True
                except ValueError:
                    # name override
                    self.logger.debug(f"Connection value is not json, enable name override for {connection_name}.")
                    connections_name_overrides[connection_name] = override_conn
                if data_override:
                    try:
                        # try best to convert to connection, this is only for azureml deployment.
                        from promptflow.core._connection_provider._workspace_connection_provider import (
                            WorkspaceConnectionProvider,
                        )

                        conn = WorkspaceConnectionProvider._convert_to_connection_dict(connection_name, conn_data)
                        connections[connection_name] = conn
                    except Exception as e:
                        self.logger.warning(f"Failed to convert connection data to connection: {e}")
                        raise InvalidConnectionData(connection_name)
        if len(connections_name_overrides) > 0:
            self.logger.info(f"Connection name overrides: {connections_name_overrides}")
        if len(connections) > 0:
            self.logger.info(f"Connections data overrides: {connections.keys()}")
        self.connections.update(connections)
        return self.connections, connections_name_overrides

    def raise_ex_on_invoker_initialization_failure(self, ex: Exception):
        from promptflow.core._errors import UserAuthenticationError

        # allow lazy authentication for UserAuthenticationError
        return not isinstance(ex, UserAuthenticationError)

    def get_user_agent(self) -> str:
        return USER_AGENT

    def get_metrics_common_dimensions(self):
        return self.common_dimensions

    def get_credential(self):
        return self.credential

    def _get_env_connections_if_exist(self):
        # For local test app connections will be set.
        connections = {}
        env_connections = get_pf_serving_env("PROMPTFLOW_ENCODED_CONNECTIONS")
        if env_connections:
            connections = decode_dict(env_connections)
        return connections

    def _initialize_connection_provider(self):
        # parse connection provider
        self.connection_provider = get_pf_serving_env("PROMPTFLOW_CONNECTION_PROVIDER")
        if not self.connection_provider:
            pf_override = os.getenv("PRT_CONFIG_OVERRIDE", None)
            if pf_override:
                env_conf = pf_override.split(",")
                env_conf_list = [setting.split("=") for setting in env_conf]
                settings = {setting[0]: setting[1] for setting in env_conf_list}
                self.subscription_id = settings.get("deployment.subscription_id", None)
                self.resource_group = settings.get("deployment.resource_group", None)
                self.workspace_name = settings.get("deployment.workspace_name", None)
                self.endpoint_name = settings.get("deployment.endpoint_name", None)
                self.deployment_name = settings.get("deployment.deployment_name", None)
            else:
                deploy_resource_id = os.getenv("AML_DEPLOYMENT_RESOURCE_ID", None)
                if deploy_resource_id:
                    match_result = re.match(AML_DEPLOYMENT_RESOURCE_ID_REGEX, deploy_resource_id)
                    if len(match_result.groups()) == 5:
                        self.subscription_id = match_result.group(1)
                        self.resource_group = match_result.group(2)
                        self.workspace_name = match_result.group(3)
                        self.endpoint_name = match_result.group(4)
                        self.deployment_name = match_result.group(5)
                else:
                    # raise exception if not found any valid connection provider setting
                    raise MissingConnectionProvider(
                        message="Missing connection provider, please check whether 'PROMPTFLOW_CONNECTION_PROVIDER' "
                        "is in your environment variable list."
                    )  # noqa: E501
            self.connection_provider = AML_WORKSPACE_TEMPLATE.format(
                self.subscription_id, self.resource_group, self.workspace_name
            )  # noqa: E501


def _get_managed_identity_credential_with_retry(**kwargs):
    from azure.identity import ManagedIdentityCredential
    from azure.identity._constants import EnvironmentVariables

    class ManagedIdentityCredentialWithRetry(ManagedIdentityCredential):
        def __init__(self, **kwargs: Any) -> None:
            client_id = kwargs.pop("client_id", None) or os.environ.get(EnvironmentVariables.AZURE_CLIENT_ID)
            super().__init__(client_id=client_id, **kwargs)

        @retry(Exception)
        def get_token(self, *scopes, **kwargs):
            return super().get_token(*scopes, **kwargs)

    return ManagedIdentityCredentialWithRetry(**kwargs)
