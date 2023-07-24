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

CREATE_UNREGISTERED_OUTPUT_URL = (
    "{endpoint}/data/v1.0/subscriptions/{sub}/resourceGroups/{rg}/"
    "providers/Microsoft.MachineLearningServices/workspaces/{ws}/dataversion/createUnregisteredOutput"
)


class AssetSystemError(SystemErrorException):
    def __init__(self, message):
        super().__init__(message, target=ErrorTarget.RUNTIME)


class AssetClient:
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
        return AssetClient(
            subscription_id=runtime_config.deployment.subscription_id,
            resource_group=runtime_config.deployment.resource_group,
            workspace_name=runtime_config.deployment.workspace_name,
            service_endpoint=runtime_config.deployment.mt_service_endpoint,
            credential=get_default_credential(),
            runtime_config=runtime_config,
        )

    @retry(AssetSystemError, tries=3, logger=logger)
    def create_unregistered_output(
        self, run_id, datastore_name, relative_path, output_name="flow_outputs", type="UriFolder"
    ):
        try:
            url = CREATE_UNREGISTERED_OUTPUT_URL.format(
                endpoint=self.service_endpoint,
                sub=self.subscription_id,
                rg=self.resource_group,
                ws=self.workspace_name,
            )

            logger.info(f"Creating unregistered output Asset for Run {run_id}...")
            token = self.credential.get_token(MANAGEMENT_OAUTH_SCOPE)
            headers = {"Authorization": "Bearer %s" % (token.token)}

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

            response = requests.post(url, headers=headers, json=payload)

            if response.status_code != 200:
                logger.error(
                    "Failed to create unregistered Asset for Run %s. Code=%s. Message={customer_content}",
                    run_id,
                    response.status_code,
                    extra={"customer_content": response.text},
                )
            elif response.status_code == 401 or response.status_code == 403:
                if self.runtime_config:
                    auth_error_message = self.runtime_config._get_auth_error_message(RuntimeAuthErrorType.WORKSPACE)
                else:
                    auth_error_message = response.text
                # if it's auth issue, return auth_error_message
                raise UserAuthenticationError(message=auth_error_message, target=ErrorTarget.RUNTIME)
            elif response.status_code != 200:
                raise Exception(
                    "Failed to create unregistered Asset for Run {}. Code={}. Message={}".format(
                        run_id, response.status_code, response.text
                    )
                )

            asset_id = response.json()["latestVersion"]["dataVersion"]["assetId"]
            return asset_id
        except UserErrorException:
            logger.exception("Create unregistered Asset for Run %s failed with user error.", run_id)
            raise
        except Exception as ex:
            logger.error(
                "Create unregistered Asset for Run %s failed. exception={customer_content}",
                run_id,
                extra={"customer_content": ex},
                exc_info=True,
            )
            raise AssetSystemError(f"Failed to create unregistered Asset for {run_id}: {str(ex)}") from ex
