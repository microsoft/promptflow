import asyncio
import tempfile
from pathlib import Path
from typing import Dict

from azure.core.exceptions import HttpResponseError, ResourceExistsError
from azure.storage.blob.aio import BlobServiceClient

from promptflow._cli._utils import merge_jsonl_files
from promptflow._constants import OutputsFolderName
from promptflow._sdk._constants import Local2Cloud, LocalStorageFilenames
from promptflow._sdk._errors import UploadInternalError, UploadUserError, UserAuthenticationError
from promptflow._sdk.entities import Run
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow.azure._storage.blob.client import _get_datastore_credential
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
        self.datastore = self._get_datastore_with_secrets()
        self.blob_service_client = self._init_blob_service_client()

    def _get_datastore_with_secrets(self):
        operations = self.run_ops._datastore_operations
        datastore = operations.get_default(include_secrets=True)
        cred = getattr(datastore.credentials, "account_key", None)
        if not cred:
            raise UploadInternalError(f"Datastore {datastore.name!r} does not have valid account key.")
        return datastore

    def _init_blob_service_client(self):
        logger.debug("Initializing blob service client.")
        account_url = f"{self.datastore.account_name}.blob.{self.datastore.endpoint}"
        # use credential from datastore, in this way user does not need RBAC role "Storage Blob Data Contributor"
        # to perform write operation on the blob storage.
        credential = _get_datastore_credential(self.datastore, self.run_ops._datastore_operations)
        return BlobServiceClient(account_url=account_url, credential=credential)

    async def upload(self) -> Dict:
        """Upload run record to cloud."""
        error_msg_prefix = f"Failed to upload run {self.run.name!r}"
        try:
            async with self.blob_service_client:
                # upload other artifacts
                tasks = [
                    # put async functions in tasks to run in coroutines
                    self._upload_flow_artifacts(),
                    self._upload_node_artifacts(),
                    self._upload_run_outputs(),
                    # self._upload_run_snapshot(httpx_client),
                ]
                results = await asyncio.gather(*tasks)

                # merge the results to be a dict
                result_dict = {
                    OutputsFolderName.FLOW_ARTIFACTS: results[0],
                    OutputsFolderName.NODE_ARTIFACTS: results[1],
                    OutputsFolderName.FLOW_OUTPUTS: results[2],
                }
                return result_dict

        except UserAuthenticationError:
            raise
        except UploadUserError:
            raise
        except Exception as e:
            raise UploadInternalError(f"{error_msg_prefix}. Error: {e}") from e

    async def _upload_flow_artifacts(self) -> str:
        """Upload run artifacts to cloud."""
        logger.debug(f"Uploading flow artifacts for run {self.run.name!r}.")
        # need to merge jsonl files before uploading
        with tempfile.TemporaryDirectory() as temp_dir:
            local_folder = self.run_output_path / f"{OutputsFolderName.FLOW_ARTIFACTS}"
            temp_local_folder = Path(temp_dir) / f"{OutputsFolderName.FLOW_ARTIFACTS}"
            logger.debug("Merging run artifacts jsonl files.")
            merge_jsonl_files(local_folder, temp_local_folder)
            remote_folder = f"{Local2Cloud.BLOB_ROOT}/{Local2Cloud.BLOB_ARTIFACTS}/{self.run.name}"
            # upload the artifacts folder to blob
            await self._upload_local_folder_to_blob(temp_local_folder, remote_folder)
        return f"{remote_folder}/{OutputsFolderName.FLOW_ARTIFACTS}"

    async def _upload_node_artifacts(self) -> str:
        logger.debug(f"Uploading node artifacts for run {self.run.name!r}.")
        local_folder = self.run_output_path / f"{OutputsFolderName.NODE_ARTIFACTS}"
        remote_folder = f"{Local2Cloud.BLOB_ROOT}/{Local2Cloud.BLOB_ARTIFACTS}/{self.run.name}"
        await self._upload_local_folder_to_blob(local_folder, remote_folder)
        return f"{remote_folder}/{OutputsFolderName.NODE_ARTIFACTS}"

    async def _upload_run_outputs(self) -> str:
        """Upload run outputs to cloud."""
        logger.debug(f"Uploading run outputs for run {self.run.name!r}.")
        local_folder = self.run_output_path / f"{OutputsFolderName.FLOW_OUTPUTS}"
        remote_folder = f"{Local2Cloud.BLOB_ROOT}/{Local2Cloud.BLOB_ARTIFACTS}/{self.run.name}"
        await self._upload_local_folder_to_blob(local_folder, remote_folder)
        return f"{remote_folder}/{OutputsFolderName.FLOW_OUTPUTS}"

    async def _upload_logs(self) -> str:
        """Upload logs to cloud."""
        logger.debug(f"Uploading logs for run {self.run.name!r}.")
        local_folder = self.run_output_path / "logs"
        remote_folder = f"{Local2Cloud.BLOB_ROOT}/{Local2Cloud.BLOB_LOGS}/{self.run.name}"
        await self._upload_local_folder_to_blob(local_folder, remote_folder)

    async def _upload_snapshot(self) -> str:
        """Upload run snapshot to cloud."""
        logger.debug(f"Uploading snapshot for run {self.run.name!r}.")
        local_folder = self.run_output_path / LocalStorageFilenames.SNAPSHOT_FOLDER
        remote_folder = f"{Local2Cloud.BLOB_ROOT}/{Local2Cloud.BLOB_SNAPSHOT}/{self.run.name}"
        await self._upload_local_folder_to_blob(local_folder, remote_folder)

    async def _upload_metrics(self) -> None:
        """Upload run metrics to cloud."""
        logger.debug(f"Uploading metrics for run {self.run.name!r}.")
        local_folder = self.run_output_path / LocalStorageFilenames.METRICS
        remote_folder = f"{Local2Cloud.BLOB_ROOT}/{Local2Cloud.BLOB_METRICS}/{self.run.name}"
        await self._upload_local_folder_to_blob(local_folder, remote_folder)

    async def _upload_local_folder_to_blob(self, local_folder, remote_folder):
        """Upload local folder to remote folder in blob.

        Note:
            If local folder is "a/b/c", and remote folder is "x/y/z", the blob path will be "x/y/z/c".
        """
        logger.debug(f"Uploading local folder {local_folder.resolve().as_posix()!r} to blob {remote_folder!r}.")
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
                await self._upload_local_file_to_blob(file, blob_path)

        # return the remote folder path
        return f"{remote_folder}/{local_folder.name}"

    async def _upload_local_file_to_blob(self, local_file, remote_file):
        """Upload local file to remote file in blob."""
        local_file = Path(local_file)

        if not local_file.is_file():
            raise UploadInternalError(
                f"Local file {local_file.resolve().as_posix()!r} does not exist or it's not a file."
            )

        # Create a blob client for the blob path
        blob_client = self.blob_service_client.get_blob_client(
            container=self.datastore.container_name, blob=remote_file
        )
        # Upload the file to the blob
        await self._upload_single_blob(blob_client, local_file)

    async def _upload_single_blob(self, blob_client, data_path) -> None:
        """Upload a single blob to cloud."""
        logger.debug(f"Uploading local file {data_path.resolve().as_posix()!r} to blob {blob_client.blob_name!r}.")
        data_path = Path(data_path)
        if not data_path.is_file():
            UploadInternalError(f"Data path {data_path.resolve().as_posix()!r} does not exist or it's not a file.")

        async with blob_client:
            with open(data_path, "rb") as f:
                try:
                    await blob_client.upload_blob(f, overwrite=self.overwrite)
                except ResourceExistsError as e:
                    error_msg = (
                        f"Failed to upload run {self.run.name!r}. "
                        f"Specified blob {blob_client.blob_name!r} already exists and overwrite is set to False. "
                        f"Container: {blob_client.container_name!r}. Datastore: {self.datastore.name!r}."
                    )
                    raise UploadUserError(error_msg) from e
                except HttpResponseError as e:
                    if e.status_code == 403:
                        raise UserAuthenticationError(
                            f"Failed to upload run {self.run.name!r}. "
                            f"User does not have permission to perform write operation on storage account "
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
