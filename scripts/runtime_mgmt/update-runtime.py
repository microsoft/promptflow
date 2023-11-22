# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse
import time
from pathlib import Path

import requests
from azure.ai.ml import MLClient, load_environment
from azure.identity import AzureCliCredential

ENVIRONMENT_YAML = Path(__file__).parent / "runtime-env" / "env.yaml"

EXAMPLE_RUNTIME_NAME = "example-runtime-ci"
TEST_RUNTIME_NAME = "test-runtime-ci"


class PFSRuntimeHelper:
    def __init__(self, ml_client: MLClient):
        subscription_id = ml_client._operation_scope.subscription_id
        resource_group_name = ml_client._operation_scope.resource_group_name
        workspace_name = ml_client._operation_scope.workspace_name
        location = ml_client.workspaces.get().location
        self._request_url_prefix = (
            f"https://{location}.api.azureml.ms/flow/api/subscriptions/{subscription_id}"
            f"/resourceGroups/{resource_group_name}/providers/Microsoft.MachineLearningServices"
            f"/workspaces/{workspace_name}/FlowRuntimes"
        )
        token = ml_client._credential.get_token("https://management.azure.com/.default").token
        self._headers = {"Authorization": f"Bearer {token}"}

    def update_runtime(self, name: str, env_asset_id: str) -> None:
        body = {
            "runtimeDescription": "Runtime hosted on compute instance, serves for examples checks.",
            "environment": env_asset_id,
            "instanceCount": "",
        }
        response = requests.put(
            f"{self._request_url_prefix}/{name}",
            headers=self._headers,
            json=body,
        )
        response.raise_for_status()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", help="Path to config.json", type=str)
    return parser.parse_args()


def init_ml_client(
    subscription_id: str,
    resource_group_name: str,
    workspace_name: str,
) -> MLClient:
    return MLClient(
        credential=AzureCliCredential(),
        subscription_id=subscription_id,
        resource_group_name=resource_group_name,
        workspace_name=workspace_name,
    )


def create_environment(ml_client: MLClient) -> str:
    environment = load_environment(source=ENVIRONMENT_YAML)
    env = ml_client.environments.create_or_update(environment)

    # have observed delay between environment creation and asset id availability
    while True:
        try:
            ml_client.environments.get(name=env.name, version=env.version)
            break
        except Exception:
            time.sleep(10)

    # get workspace id from REST workspace object
    resource_group_name = ml_client._operation_scope.resource_group_name
    workspace_name = ml_client._operation_scope.workspace_name
    location = ml_client.workspaces.get().location
    workspace_id = ml_client._workspaces._operation.get(
        resource_group_name=resource_group_name, workspace_name=workspace_name
    ).workspace_id
    # concat environment asset id
    asset_id = (
        f"azureml://locations/{location}/workspaces/{workspace_id}"
        f"/environments/{env.name}/versions/{env.version}"
    )
    return asset_id


def main(args: argparse.Namespace):
    subscription_id, resource_group_name, workspace_name = MLClient._get_workspace_info(args.path)
    ml_client = init_ml_client(
        subscription_id=subscription_id,
        resource_group_name=resource_group_name,
        workspace_name=workspace_name,
    )
    pfs_runtime_helper = PFSRuntimeHelper(ml_client=ml_client)

    print("creating environment...")
    env_asset_id = create_environment(ml_client=ml_client)
    print("created environment, asset id:", env_asset_id)

    print("updating runtime for test...")
    pfs_runtime_helper.update_runtime(name=TEST_RUNTIME_NAME, env_asset_id=env_asset_id)
    print("updating runtime for example...")
    pfs_runtime_helper.update_runtime(name=EXAMPLE_RUNTIME_NAME, env_asset_id=env_asset_id)
    print("runtime updated!")


if __name__ == "__main__":
    main(args=parse_args())
