# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from typing import Dict

import httpx

from promptflow._sdk._errors import MetricInternalError, SDKError, UserAuthenticationError
from promptflow._sdk._utilities.general_utils import get_promptflow_sdk_version
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow._utils.retry_utils import async_retry
from promptflow.azure._utils.general import get_authorization

logger = get_cli_sdk_logger()

POST_METRICS_URL = (
    "{endpoint}/metric/v2.0/subscriptions/{sub}/resourceGroups/{rg}/"
    "providers/Microsoft.MachineLearningServices/workspaces/{ws}/runs/{runId}/batchsync"
)


class AsyncMetricClient:
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

    @async_retry(MetricInternalError, _logger=logger)
    async def log_metric(self, run_id, metric_key: str, metric_value: float):
        """Write metric for a run."""
        url = POST_METRICS_URL.format(
            sub=self.subscription_id,
            rg=self.resource_group,
            ws=self.workspace_name,
            endpoint=self.service_endpoint,
            runId=run_id,
        )

        logger.debug(f"Writing metrics '{metric_key}:{metric_value}' for Run {run_id!r}...")

        payload = {
            "values": [
                {
                    "name": metric_key,
                    "columns": {metric_key: "Double"},
                    "properties": {"uxMetricType": "azureml.v1.scalar"},
                    "value": [{"data": {metric_key: metric_value}, "step": 0}],
                }
            ]
        }

        error_msg_prefix = f"Failed to write metrics '{metric_key}:{metric_value}' for Run {run_id!r}"
        try:
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.post(url, headers=self._get_header(), json=payload)
                if response.status_code == 401 or response.status_code == 403:
                    # if it's auth issue, return auth_error_message
                    raise UserAuthenticationError(response.text)
                elif response.status_code != 200:
                    error_message = f"{error_msg_prefix}. Code={response.status_code}. Message={response.text}"
                    raise MetricInternalError(error_message)
        except Exception as e:
            error_message = f"{error_msg_prefix}: {str(e)}"
            raise MetricInternalError(error_message) from e

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
