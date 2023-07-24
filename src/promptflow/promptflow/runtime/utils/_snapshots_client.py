# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import os
import time
import zipfile
from pathlib import Path

import requests
from azure.storage.blob import BlobServiceClient
from six.moves.urllib import parse

from promptflow.exceptions import UserAuthenticationError, UserErrorException
from promptflow.runtime.error_codes import DownloadSnapshotFailed, GetSnapshotSasUrlFailed, SnapshotNotFound
from promptflow.runtime.runtime_config import RuntimeConfig
from promptflow.runtime.utils import logger
from promptflow.runtime.utils._token_utils import MANAGEMENT_OAUTH_SCOPE, get_default_credential
from promptflow.storage.azureml_run_storage import RuntimeAuthErrorType
from promptflow.utils.retry_utils import retry

SNAPSHOT_ZIP_URL = (
    "{endpoint}/content/v2.0/subscriptions/{sub}/resourceGroups/{rg}/"
    "providers/Microsoft.MachineLearningServices/workspaces/{ws}/snapshots/{snapshot_id}/zip"
)
ZIP_WAITING_INTERVAL = 3


class SnapshotsClient:
    def __init__(self, runtime_config: RuntimeConfig):
        self.credential = get_default_credential()
        self.subscription_id = runtime_config.deployment.subscription_id
        self.resource_group = runtime_config.deployment.resource_group
        self.workspace_name = runtime_config.deployment.workspace_name
        self.service_endpoint = runtime_config.deployment.mt_service_endpoint
        self.runtime_config = runtime_config

    @retry(DownloadSnapshotFailed, tries=3, logger=logger)
    def download_snapshot(self, snapshot_id: str, target_path: Path):
        try:
            zip_url = SNAPSHOT_ZIP_URL.format(
                endpoint=self.service_endpoint,
                sub=self.subscription_id,
                rg=self.resource_group,
                ws=self.workspace_name,
                snapshot_id=snapshot_id,
            )

            logger.info(f"Get snapshot sas url for {snapshot_id}...")
            token = self.credential.get_token(MANAGEMENT_OAUTH_SCOPE)
            headers = {"Authorization": "Bearer %s" % (token.token)}

            response = requests.post(zip_url, headers=headers)
            if response.status_code == 202:
                data = json.loads(response.content)
                location = data["location"]

            while response.status_code == 202:
                response = requests.get(location, headers=headers)
                time.sleep(ZIP_WAITING_INTERVAL)

            if response.status_code != 200:
                logger.error(
                    "Failed to get snapshot sas url for %s. Code=%s. Message={customer_content}",
                    snapshot_id,
                    response.status_code,
                    extra={"customer_content": response.text},
                )

            if response.status_code == 404:
                raise SnapshotNotFound(message=response.text)
            elif response.status_code == 401 or response.status_code == 403:
                auth_error_message = self.runtime_config._get_auth_error_message(RuntimeAuthErrorType.WORKSPACE)
                # if it's auth issue, return auth_error_message
                raise UserAuthenticationError(message=auth_error_message)
            elif response.status_code != 200:
                raise GetSnapshotSasUrlFailed(
                    message_format=(
                        "Failed to get snapshot sas url for {snapshot_id}. Code={status_code}. Message={msg}"
                    ),
                    snapshot_id=snapshot_id,
                    status_code=response.status_code,
                    msg=response.text,
                )

            data = json.loads(response.content)
            zip_sas_uri = data.get("zipSasUri", "")
            blob_uri = zip_sas_uri[: zip_sas_uri.find("?")]
            logger.info(f"Downloading snapshot {snapshot_id} from uri {blob_uri}...")

            sas_token, account_name, endpoint_suffix, container_name, blob_name = get_block_blob_service_credentials(
                zip_sas_uri
            )

            account_url = "https://{account_name}.blob.{endpoint}".format(
                account_name=account_name, endpoint=endpoint_suffix
            )
            blob_service = BlobServiceClient(account_url=account_url, credential=sas_token)

            blob_client = blob_service.get_blob_client(container=container_name, blob=blob_name)
            download_path = target_path / (snapshot_id + ".zip")
            download_stream = blob_client.download_blob(max_concurrency=8, validate_content=False)
            download_path.write_bytes(download_stream.readall())
            file_size = os.stat(download_path).st_size
            logger.info(
                "Downloaded file {} with size {} for snapshot {}.".format(download_path, file_size, snapshot_id)
            )

            with zipfile.ZipFile(download_path.as_posix(), "r") as zipf:
                zipf.extractall(target_path)
            logger.info(f"Downloade snapshot {snapshot_id} completed.")
        except UserErrorException:
            logger.exception("Download snapshot %s failed with user error.", snapshot_id)
            raise
        except Exception as ex:
            logger.error("Download snapshot %s failed. exception=%s", snapshot_id, ex, exc_info=True)
            raise DownloadSnapshotFailed(
                message_format="Failed to download snapshot {snapshot_id}: {exception_message}",
                snapshot_id=snapshot_id,
                exception_message=str(ex),
            ) from ex


def get_block_blob_service_credentials(sas_url):
    parsed_url = parse.urlparse(sas_url)

    sas_token = parsed_url.query

    # Split the netloc into 3 parts: acountname, "blob", endpoint_suffix
    # https://docs.microsoft.com/en-us/rest/api/storageservices/create-service-sas#service-sas-example
    account_name, _, endpoint_suffix = parsed_url.netloc.split(".", 2)

    path = parsed_url.path
    # Remove leading / to avoid awkward parse
    if path[0] == "/":
        path = path[1:]
    container_name, blob_name = path.split("/", 1)

    return sas_token, account_name, endpoint_suffix, container_name, blob_name
