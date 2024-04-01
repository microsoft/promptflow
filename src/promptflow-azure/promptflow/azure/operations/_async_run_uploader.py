import asyncio
import tempfile
from pathlib import Path

from azure.core.exceptions import HttpResponseError, ResourceExistsError
from azure.storage.blob.aio import BlobServiceClient

from promptflow._cli._utils import merge_jsonl_files
from promptflow._constants import OutputsFolderName
from promptflow._sdk._constants import AzureRunTypes, Local2Cloud
from promptflow._sdk._errors import UploadInternalError, UserAuthenticationError
from promptflow._sdk.entities import Run
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow.azure._utils._asset_client import AsyncAssetClient
from promptflow.azure._utils._run_history_client import AsyncRunHistoryClient
from promptflow.exceptions import UserErrorException

logger = get_cli_sdk_logger()


class AsyncRunUploader:
    """Upload local run record to cloud"""

    IGNORED_PATTERN = ["__pycache__"]

    def __init__(self, run: Run, run_ops: "RunOperations", overwrite=True):
        self.run = run
        self.run_output_path = Path(run.properties["output_path"])
        self.run_ops = run_ops
        self.overwrite = overwrite
        self.datastore = run_ops._workspace_default_datastore
        self.blob_service_client = self._init_blob_service_client()
        self.run_history_client = AsyncRunHistoryClient.from_run_operations(run_ops)
        self.asset_client = AsyncAssetClient.from_run_operations(run_ops)

    def _init_blob_service_client(self):
        logger.debug("Initializing blob service client.")
        account_url = f"{self.datastore.account_name}.blob.{self.datastore.endpoint}"
        return BlobServiceClient(account_url=account_url, credential=self.run_ops._credential)

    async def upload(self) -> None:
        """Upload run record to cloud."""
        error_msg_prefix = f"Failed to upload run {self.run.name!r}"
        try:
            # pass verify=False to client to disable SSL verification.
            # Source: https://github.com/encode/httpx/issues/1331
            async with self.blob_service_client:
                # create run history record
                await self._create_run_history_record()
                # upload other artifacts
                tasks = [
                    # put async functions in tasks to run in coroutines
                    self._upload_run_artifacts(),
                    # self._upload_run_snapshot(httpx_client),
                ]
                await asyncio.gather(*tasks)
        except UserAuthenticationError:
            raise
        except Exception as e:
            raise UploadInternalError(f"{error_msg_prefix}. Error: {e}") from e

    async def _create_run_history_record(self) -> None:
        """Create run history record"""
        logger.debug(f"Creating run history record for run {self.run.name!r}.")
        # set run property to label the run as local to cloud
        properties = dict()
        properties[Local2Cloud.PROPERTY_KEY] = "true"

        # prepare the payload
        payload = {
            "runId": self.run.name,
            "status": self.run.status,
            "runType": AzureRunTypes.EVALUATION if self.run.run else AzureRunTypes.BATCH,
            "displayName": self.run.display_name,
            "description": self.run.description,
            "properties": properties,
            "tags": self.run.tags,
        }
        payload = {k: v for k, v in payload.items() if v}
        await self.run_history_client.patch_run(payload)
        logger.debug(f"Successfully created run history record for run {self.run.name!r}.")

    async def _update_run_record_with_artifacts_asset_id(self, asset_id):
        """Update run record with artifacts asset id"""
        logger.debug(f"Updating run record {self.run.name!r} with artifacts asset id {asset_id!r}.")
        payload = {
            "runId": self.run.name,
            "Outputs": {Local2Cloud.ASSET_NAME_DEBUG_INFO: {"assetId": asset_id, "type": "UriFolder"}},
        }
        await self.run_history_client.patch_run(payload)

    async def _upload_run_artifacts(self) -> None:
        """Upload run artifacts to cloud."""
        with tempfile.TemporaryDirectory() as temp_dir:
            local_folder = self.run_output_path / f"{OutputsFolderName.FLOW_ARTIFACTS}"
            temp_local_folder = Path(temp_dir) / f"{OutputsFolderName.FLOW_ARTIFACTS}"
            # need to merge jsonl files before uploading
            merge_jsonl_files(local_folder, temp_local_folder)
            remote_folder = f"{Local2Cloud.BLOB_ROOT}/{Local2Cloud.BLOB_ARTIFACTS}/{self.run.name}"
            # upload the artifacts folder to blob
            await self._upload_local_folder_to_blob(temp_local_folder, remote_folder)
        # create asset for the artifacts folder
        asset_id = await self._create_asset(remote_folder, Local2Cloud.ASSET_NAME_DEBUG_INFO)
        # update flow artifacts asset id to the run record
        await self._update_run_record_with_artifacts_asset_id(asset_id)

    async def _create_asset(self, relative_path, output_name):
        asset_id = await self.asset_client.create_unregistered_output(
            run_id=self.run.name,
            datastore_name=self.datastore.name,
            relative_path=relative_path,
            output_name=output_name,
        )
        logger.debug(f"Created {output_name} Asset: {asset_id}")
        return asset_id

    async def _upload_local_folder_to_blob(self, local_folder, remote_folder):
        """Upload local folder to remote folder in blob.

        Note:
            If local folder is "a/b/c", and remote folder is "x/y/z", the blob path will be "x/y/z/c".
        """
        local_folder = Path(local_folder)

        if not local_folder.is_dir():
            raise UploadInternalError(
                f"Local folder {local_folder.resolve().as_posix()!r} does not exist or it's not a directory."
            )

        for file in local_folder.rglob("*"):
            # skip the file if it's in the ignored pattern
            skip_this_file = False
            for pattern in self.IGNORED_PATTERN:
                if pattern in file.parts:
                    skip_this_file = True
                    break
            if skip_this_file:
                continue

            # upload the file
            if file.is_file():
                # Construct the blob path
                relative_path = file.relative_to(local_folder)
                blob_path = f"{remote_folder}/{local_folder.name}/{relative_path}"

                # Create a blob client for the blob path
                blob_client = self.blob_service_client.get_blob_client(
                    container=self.datastore.container_name, blob=blob_path
                )
                # Upload the file to the blob
                await self._upload_single_blob(blob_client, file)

        # return the remote folder path
        return f"{remote_folder}/{local_folder.name}"

    async def _upload_single_blob(self, blob_client, data_path) -> None:
        """Upload a single blob to cloud."""
        data_path = Path(data_path)
        if not data_path.is_file():
            UploadInternalError(f"Data path {data_path.resolve().as_posix()!r} does not exist or it's not a file.")

        async with blob_client:
            with open(data_path, "rb") as f:
                try:
                    await blob_client.upload_blob(f, overwrite=self.overwrite)
                except ResourceExistsError as e:
                    error_msg = (
                        f"Specified blob {blob_client.blob_name!r} already exists and overwrite is set to False. "
                        f"Container: {blob_client.container_name!r}. Datastore: {self.datastore.name!r}."
                    )
                    raise UploadInternalError(error_msg) from e
                except HttpResponseError as e:
                    if e.status_code == 403:
                        raise UserAuthenticationError(
                            f"User does not have permission to perform this operation on storage account "
                            f"{self.datastore.account_name!r} container {self.datastore.container_name!r}. "
                            f"Original azure blob error: {str(e)}"
                        )
                    raise

    @classmethod
    def _from_run_operations(cls, run: Run, run_ops: "RunOperations"):
        """Create an instance from run operations."""
        from azure.ai.ml.entities._datastore.azure_storage import AzureBlobDatastore

        datastore = run_ops._workspace_default_datastore
        if isinstance(datastore, AzureBlobDatastore):
            return cls(run=run, run_ops=run_ops)
        else:
            raise UserErrorException(
                f"Cannot upload run {run.name!r} because the workspace default datastore is not supported. "
                f"Supported ones are ['AzureBlobDatastore'], got {type(datastore).__name__!r}."
            )
