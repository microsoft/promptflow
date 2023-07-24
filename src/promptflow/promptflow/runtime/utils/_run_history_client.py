# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import requests

from promptflow.exceptions import ErrorTarget, SystemErrorException, UserAuthenticationError, UserErrorException
from promptflow.runtime.runtime_config import RuntimeConfig
from promptflow.runtime.utils import logger
from promptflow.runtime.utils._token_utils import MANAGEMENT_OAUTH_SCOPE, get_default_credential
from promptflow.storage.azureml_run_storage import RuntimeAuthErrorType
from promptflow.utils.retry_utils import retry

PATCH_RUN_URL = (
    "{endpoint}/history/v1.0/subscriptions/{sub}/resourceGroups/{rg}/"
    "providers/Microsoft.MachineLearningServices/workspaces/{ws}/runs/{run_id}"
)


class RunNotFoundError(UserErrorException):
    def __init__(self, message):
        super().__init__(message, target=ErrorTarget.RUNTIME)


class RunHistorySystemError(SystemErrorException):
    def __init__(self, message):
        super().__init__(message, target=ErrorTarget.RUNTIME)


class RunHistoryClient:
    def __init__(
        self,
        subscription_id,
        resource_group,
        workspace_name,
        service_endpoint,
        credential=None,
        runtime_config: RuntimeConfig = None,
    ):
        self.subscription_id = subscription_id
        self.resource_group = resource_group
        self.workspace_name = workspace_name
        self.service_endpoint = service_endpoint
        self.credential = credential
        self.runtime_config = runtime_config

    @classmethod
    def init_from_runtime_config(self, runtime_config: RuntimeConfig):
        return RunHistoryClient(
            subscription_id=runtime_config.deployment.subscription_id,
            resource_group=runtime_config.deployment.resource_group,
            workspace_name=runtime_config.deployment.workspace_name,
            service_endpoint=runtime_config.deployment.mt_service_endpoint,
            credential=get_default_credential(),
            runtime_config=runtime_config,
        )

    @retry(RunHistorySystemError, tries=3, logger=logger)
    def patch_run(self, run_id, asset_id, output_name="flow_outputs", data_type="UriFolder"):
        try:
            patch_url = PATCH_RUN_URL.format(
                endpoint=self.service_endpoint,
                sub=self.subscription_id,
                rg=self.resource_group,
                ws=self.workspace_name,
                run_id=run_id,
            )

            logger.info(f"Patching {run_id}...")
            token = self.credential.get_token(MANAGEMENT_OAUTH_SCOPE)
            headers = {"Authorization": "Bearer %s" % (token.token)}

            payload = {"Outputs": {output_name: {"assetId": asset_id, "type": data_type}}}

            response = requests.patch(patch_url, headers=headers, json=payload)

            if response.status_code != 200:
                logger.error(
                    "Failed to patch Run %s. Code=%s. Message={customer_content}",
                    run_id,
                    response.status_code,
                    extra={"customer_content": response.text},
                )
            if response.status_code == 404:
                raise RunNotFoundError(response.text)
            elif response.status_code == 401 or response.status_code == 403:
                if self.runtime_config:
                    auth_error_message = self.runtime_config._get_auth_error_message(RuntimeAuthErrorType.WORKSPACE)
                else:
                    auth_error_message = response.text
                # if it's auth issue, return auth_error_message
                raise UserAuthenticationError(message=auth_error_message, target=ErrorTarget.RUNTIME)
            elif response.status_code != 200:
                raise Exception(
                    "Failed to patch Run {}. Code={}. Message={}".format(run_id, response.status_code, response.text)
                )
        except UserErrorException:
            logger.exception("Patch Run %s failed with user error.", run_id)
            raise
        except Exception as ex:
            logger.error(
                "Patch Run %s failed. exception={customer_content}",
                run_id,
                extra={"customer_content": ex},
                exc_info=True,
            )
            raise RunHistorySystemError(f"Failed to patch Run {run_id}: {str(ex)}") from ex
