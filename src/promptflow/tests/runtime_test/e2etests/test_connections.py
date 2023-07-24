import os

import pytest
from azure.ai.ml import MLClient
from runtime_test._azure_utils import get_cred

from promptflow.runtime.connections import (
    build_connection_dict,
    get_used_connection_names_from_environment_variables,
    update_environment_variables_with_connections,
)


@pytest.mark.e2etest
class TestConnections:
    def test_build_workspace_connections_dict(self, connection_client: MLClient):
        connections_dict = build_connection_dict(
            credential=get_cred(),
            subscription_id=connection_client.subscription_id,
            resource_group=connection_client.resource_group_name,
            workspace_name=connection_client.workspace_name,
            connection_names={"azure_open_ai_connection"},
        )
        # Scrub value
        for item in connections_dict.values():
            # Update legacy path
            if item["module"] == "promptflow.tools.connections":
                item["module"] = "promptflow.connections"
            for k, v in item["value"].items():
                item["value"][k] = "***"
        assert connections_dict == {
            "azure_open_ai_connection": {
                "type": "AzureOpenAIConnection",
                "module": "promptflow.connections",
                "value": {
                    "api_key": "***",
                    "api_base": "***",
                    "api_type": "***",
                    "api_version": "***",
                },
            },
        }

    def test_resolve_environment_variable_with_connection(self, connection_client: MLClient):
        target_connection = "azure_open_ai_connection"
        connections = build_connection_dict(
            credential=get_cred(),
            subscription_id=connection_client.subscription_id,
            resource_group=connection_client.resource_group_name,
            workspace_name=connection_client.workspace_name,
            connection_names={target_connection},
        )
        api_base_value = connections[target_connection]["value"]["api_base"]
        env_pairs = [
            ("${azure_open_ai_connection.api_base}", api_base_value),
            ("  ${azure_open_ai_connection.api_base}  ", api_base_value),
            ("${azure_open_ai_connection.api_base}/v1", "${azure_open_ai_connection.api_base}/v1"),
            ("test.${azure_open_ai_connection.api_base}", "test.${azure_open_ai_connection.api_base}"),
            ("${azure_open_ai_connection.api_base.extra}", "${azure_open_ai_connection.api_base.extra}"),
        ]
        related_env_keys, expected_env_vals = set(), {}
        for i, (env_val, expected) in enumerate(env_pairs):
            env_key = f"MY_CONNECTION_BASE_{i}"
            os.environ[env_key] = env_val
            related_env_keys.add(env_key)
            expected_env_vals[env_key] = expected

        assert get_used_connection_names_from_environment_variables() == {target_connection}
        update_environment_variables_with_connections(connections)
        assert {k: os.environ[k] for k in related_env_keys} == expected_env_vals

    def test_public_interface(self):
        # Please DO NOT change function name or remove existing parameters for the following functions, which are used
        # by code outside promptflow-sdk.
        from promptflow.runtime.connections import (
            build_connection_dict,
            get_used_connection_names_from_environment_variables,
            update_environment_variables_with_connections,
        )

        assert callable(get_used_connection_names_from_environment_variables)
        assert callable(update_environment_variables_with_connections)
        assert callable(build_connection_dict)
