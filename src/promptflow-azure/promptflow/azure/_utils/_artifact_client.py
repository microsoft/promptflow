# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from typing import Dict

import httpx

from promptflow._sdk._errors import ArtifactInternalError, SDKError, UserAuthenticationError
from promptflow._sdk._utilities.general_utils import get_promptflow_sdk_version
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow._utils.retry_utils import async_retry
from promptflow.azure._utils.general import get_authorization

logger = get_cli_sdk_logger()

CREATE_UNREGISTERED_OUTPUT_URL = (
    "{endpoint}/artifact/v2.0/subscriptions/{sub}/resourceGroups/{rg}/"
    "providers/Microsoft.MachineLearningServices/workspaces/{ws}/artifacts/register"
)

GET_ARTIFACT_SAS_URL = (
    "{endpoint}/artifact/v2.0/subscriptions/{sub}/resourceGroups/{rg}"
    "/providers/Microsoft.MachineLearningServices/workspaces/{ws}/artifacts/{origin}/{container}/write?path={path}"
)


class AsyncArtifactClient:
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

    @async_retry(ArtifactInternalError, _logger=logger)
    async def register_artifact(self, run_id, datastore_name, relative_path, path):
        """Register an artifact for a run."""
        url = CREATE_UNREGISTERED_OUTPUT_URL.format(
            sub=self.subscription_id,
            rg=self.resource_group,
            ws=self.workspace_name,
            endpoint=self.service_endpoint,
        )

        logger.debug(f"Creating Artifact for Run {run_id}...")

        payload = {
            "origin": "ExperimentRun",
            "container": f"dcid.{run_id}",
            "path": path,
            "dataPath": {
                "dataStoreName": datastore_name,
                "relativePath": relative_path,
            },
        }
        error_msg_prefix = f"Failed to create Artifact for Run {run_id!r}"
        try:
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.post(url, headers=self._get_header(), json=payload)
                if response.status_code == 401 or response.status_code == 403:
                    # if it's auth issue, raise auth error
                    error_message = f"{error_msg_prefix}. Code={response.status_code}. Message={response.text}"
                    raise UserAuthenticationError(error_message)
                elif response.status_code != 200:
                    error_message = f"{error_msg_prefix}. Code={response.status_code}. Message={response.text}"
                    raise ArtifactInternalError(error_message)
        except Exception as e:
            error_message = f"{error_msg_prefix}: {str(e)}"
            raise ArtifactInternalError(error_message) from e

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
