# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from typing import Dict

import httpx

from promptflow._sdk._errors import AssetInternalError, SDKError, UserAuthenticationError
from promptflow._sdk._utils import get_promptflow_sdk_version
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow.azure._utils.general import get_authorization

logger = get_cli_sdk_logger()

CREATE_UNREGISTERED_OUTPUT_URL = (
    "{endpoint}/data/v1.0/subscriptions/{sub}/resourceGroups/{rg}/"
    "providers/Microsoft.MachineLearningServices/workspaces/{ws}/dataversion/createUnregisteredOutput"
)


class AsyncAssetClient:
    def __init__(
        self,
        subscription_id,
        resource_group,
        workspace_name,
        service_endpoint,
        credential,
    ):
        self.subscription_id = subscription_id
        self.resource_group = resource_group
        self.workspace_name = workspace_name
        self.service_endpoint = service_endpoint
        self.credential = credential

    async def create_unregistered_output(
        self, run_id, datastore_name, relative_path, output_name="flow_outputs", type="UriFolder"
    ):
        # pass verify=False to client to disable SSL verification.
        # Source: https://github.com/encode/httpx/issues/1331
        async with httpx.AsyncClient(verify=False) as httpx_client:
            try:
                url = CREATE_UNREGISTERED_OUTPUT_URL.format(
                    endpoint=self.service_endpoint,
                    sub=self.subscription_id,
                    rg=self.resource_group,
                    ws=self.workspace_name,
                )

                logger.debug(f"Creating unregistered output Asset for Run {run_id!r}...")
                headers = self._get_header()

                data_uri = (
                    f"azureml://subscriptions/{self.subscription_id}/resourcegroups/"
                    f"{self.resource_group}/workspaces/{self.workspace_name}/"
                    f"datastores/{datastore_name}/paths/{relative_path}"
                )
                payload = {
                    "RunId": run_id,
                    "OutputName": output_name,
                    "Type": type,
                    "Uri": data_uri,
                }

                response = await httpx_client.post(url, headers=headers, json=payload)

            except Exception as e:
                raise AssetInternalError(f"Failed to post {url!r}: {str(e)}") from e
            else:
                if response.status_code == 200:
                    asset_id = response.json()["latestVersion"]["dataVersion"]["assetId"]
                    return asset_id
                if response.status_code == 401 or response.status_code == 403:
                    raise UserAuthenticationError(
                        f"User authentication error. Code: {response.status_code}. Message: {response.text}"
                    )
                else:
                    raise AssetInternalError(
                        f"Failed to patch {url!r}. Code: {response.status_code}. Message: {response.text}"
                    )

    def _get_header(self) -> Dict[str, str]:
        headers = {
            "Authorization": get_authorization(credential=self.credential),
            "Content-Type": "application/json",
            "User-Agent": "promptflow/%s" % get_promptflow_sdk_version(),
        }
        return headers

    @classmethod
    def from_run_operations(cls, run_ops):
        from promptflow.azure.operations import RunOperations

        if not isinstance(run_ops, RunOperations):
            raise SDKError(f"run_ops should be an instance of azure RunOperations, got {type(run_ops)!r} instead.")

        return cls(
            subscription_id=run_ops._operation_scope.subscription_id,
            resource_group=run_ops._operation_scope.resource_group_name,
            workspace_name=run_ops._operation_scope.workspace_name,
            service_endpoint=run_ops._service_caller._service_endpoint[0:-1],  # remove trailing slash
            credential=run_ops._credential,
        )
