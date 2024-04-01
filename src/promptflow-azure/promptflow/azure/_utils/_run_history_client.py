# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from typing import Dict

import httpx

from promptflow._sdk._constants import Local2Cloud
from promptflow._sdk._errors import RunHistoryInternalError, SDKError, UserAuthenticationError
from promptflow._sdk._utils import get_promptflow_sdk_version
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow.azure._utils.general import get_authorization

logger = get_cli_sdk_logger()

PATCH_RUN_URL = (
    "{endpoint}/history/v1.0/subscriptions/{sub}/resourceGroups/{rg}/"
    "providers/Microsoft.MachineLearningServices/workspaces/{ws}/runs/{run_id}"
)
PATCH_EXP_RUN_URL = (
    "{endpoint}/history/v1.0/subscriptions/{sub}/resourceGroups/{rg}/"
    "providers/Microsoft.MachineLearningServices/workspaces/{ws}/experiments/{exp_name}/runs/{run_id}"
)


class AsyncRunHistoryClient:
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

    async def patch_run(self, payload: Dict):
        # pass verify=False to client to disable SSL verification.
        # Source: https://github.com/encode/httpx/issues/1331
        async with httpx.AsyncClient(verify=False) as httpx_client:
            run_id = payload.get("runId")
            logger.debug(f"Patching {run_id!r} with payload {payload!r}...")
            url = PATCH_EXP_RUN_URL.format(
                endpoint=self.service_endpoint,
                sub=self.subscription_id,
                rg=self.resource_group,
                ws=self.workspace_name,
                exp_name=Local2Cloud.EXPERIMENT_NAME,
                run_id=run_id,
            )
            headers = self._get_header()
            try:
                response = await httpx_client.patch(url, headers=headers, json=payload)
            except Exception as e:
                raise RunHistoryInternalError(f"Failed to patch {url}: {str(e)}") from e
            else:
                if response.status_code == 401 or response.status_code == 403:
                    raise UserAuthenticationError(
                        f"User authentication error. Code: {response.status_code}. Message: {response.text}"
                    )
                elif response.status_code != 200:
                    raise RunHistoryInternalError(
                        f"Failed to patch {url}. Code: {response.status_code}. Message: {response.text}"
                    )

    async def create_run(self, payload):
        url = PATCH_EXP_RUN_URL.format(
            endpoint=self.service_endpoint,
            sub=self.subscription_id,
            rg=self.resource_group,
            ws=self.workspace_name,
            exp_name="local_to_cloud",
            run_id=payload.get("runId"),
        )
        await self.patch_run(url, payload)

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
