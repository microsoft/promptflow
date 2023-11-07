# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import List

import requests
from azure.ai.ml import MLClient


class PFSRuntimeHelper:
    def __init__(self, ml_client: MLClient):
        subscription_id = ml_client._operation_scope.subscription_id
        resource_group_name = ml_client._operation_scope.resource_group_name
        workspace_name = ml_client._operation_scope.workspace_name
        location = ml_client.workspaces.get(name=workspace_name).location
        self._request_url_prefix = (
            f"https://{location}.api.azureml.ms/flow/api/subscriptions/{subscription_id}"
            f"/resourceGroups/{resource_group_name}/providers/Microsoft.MachineLearningServices"
            f"/workspaces/{workspace_name}/FlowRuntimes"
        )
        token = ml_client._credential.get_token("https://management.azure.com/.default").token
        self._headers = {"Authorization": f"Bearer {token}"}

    def list_runtimes(self) -> List[dict]:
        response = requests.get(
            self._request_url_prefix,
            headers=self._headers,
        )
        response.raise_for_status()
        return response.json()

    def create_runtime(self, name: str, env_asset_id: str, ci_name: str) -> None:
        body = {
            "runtimeType": "ComputeInstance",
            "instanceType": "",
            "environment": env_asset_id,
            "computeInstanceName": ci_name,
        }
        response = requests.post(
            f"{self._request_url_prefix}/{name}",
            headers=self._headers,
            json=body,
        )
        response.raise_for_status()

    def delete_runtime(self, name: str) -> None:
        response = requests.delete(
            f"{self._request_url_prefix}/{name}",
            headers=self._headers,
        )
        response.raise_for_status()

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
