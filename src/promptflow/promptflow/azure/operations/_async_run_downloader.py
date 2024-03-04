import asyncio
import contextvars
import functools
import json
from pathlib import Path
from typing import Optional, Union

import httpx
from azure.core.exceptions import HttpResponseError
from azure.storage.blob.aio import BlobServiceClient

from promptflow._sdk._constants import DEFAULT_ENCODING, DownloadedRun
from promptflow._sdk._errors import DownloadInternalError, RunNotFoundError, RunOperationError
from promptflow._sdk.entities import Run
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow.exceptions import UserErrorException

logger = get_cli_sdk_logger()


class AsyncRunDownloader:
    """Download run results from the service asynchronously.

    :param run: The run id.
    :type run: str
    :param run_ops: The run operations.
    :type run_ops: ~promptflow.azure.operations.RunOperations
    :param output_folder: The output folder to save the run results.
    :type output_folder: Union[Path, str]
    """

    IGNORED_PATTERN = ["__pycache__"]

    def __init__(self, run: str, run_ops: "RunOperations", output_folder: Union[str, Path]) -> None:
        self.run = run
        self.run_ops = run_ops
        self.datastore = run_ops._workspace_default_datastore
        self.output_folder = Path(output_folder)
        self.blob_service_client = self._init_blob_service_client()
        self._use_flow_outputs = False  # old runtime does not write debug_info output asset, use flow_outputs instead

    def _init_blob_service_client(self):
        logger.debug("Initializing blob service client.")
        account_url = f"{self.datastore.account_name}.blob.{self.datastore.endpoint}"
        return BlobServiceClient(account_url=account_url, credential=self.run_ops._credential)

    async def download(self) -> str:
        """Download the run results asynchronously."""
        error_msg_prefix = f"Failed to download run {self.run!r}"
        try:
            # pass verify=False to client to disable SSL verification.
            # Source: https://github.com/encode/httpx/issues/1331
            async with httpx.AsyncClient(verify=False) as client:
                tasks = [
                    # put async functions in tasks to run in coroutines
                    self._download_artifacts_and_snapshot(client),
                    # below functions are actually synchronous functions in order to reuse code
                    # and use thread pool to avoid blocking the event loop
                    to_thread(self._download_run_metrics),
                    to_thread(self._download_run_logs),
                ]
                await asyncio.gather(*tasks)
        except RunNotFoundError as e:
            raise RunOperationError(f"{error_msg_prefix}. Error: {e}") from e
        except HttpResponseError as e:
            if e.status_code == 403:
                raise RunOperationError(
                    f"{error_msg_prefix}. User does not have permission to perform this operation on storage account "
                    f"{self.datastore.account_name!r} container {self.datastore.container_name!r}. "
                    f"Original azure blob error: {str(e)}"
                )
            else:
                raise DownloadInternalError(f"{error_msg_prefix}. Error: {e}") from e
        except Exception as e:
            raise DownloadInternalError(f"{error_msg_prefix}. Error: {e}") from e

        return self.output_folder.resolve().as_posix()

    async def _download_artifacts_and_snapshot(self, httpx_client: httpx.AsyncClient):
        run_data = await self._get_run_data_from_run_history(httpx_client)

        logger.debug("Parsing run data from run history to get necessary information.")
        # extract necessary information from run data
        snapshot_id = run_data["runMetadata"]["properties"]["azureml.promptflow.snapshot_id"]
        output_data = run_data["runMetadata"]["outputs"].get("debug_info", None)
        if output_data is None:
            logger.warning(
                "Downloading run '%s' but the 'debug_info' output assets is not available, "
                "maybe because the job ran on old version runtime, trying to get `flow_outputs` output asset instead.",
                self.run,
            )
            self._use_flow_outputs = True
            output_data = run_data["runMetadata"]["outputs"].get("flow_outputs", None)
        output_asset_id = output_data["assetId"]

        # save run metadata to run_metadata.json
        logger.debug("Saving the run meta data.")
        run_data = self.run_ops._refine_run_data_from_run_history(run_data)
        run_data = Run._from_run_history_entity(run_data)
        with open(self.output_folder / DownloadedRun.RUN_METADATA_FILE_NAME, "w", encoding=DEFAULT_ENCODING) as f:
            json.dump(run_data._to_dict(), f, ensure_ascii=False)

        async with self.blob_service_client:
            container_name = self.datastore.container_name
            logger.debug("Getting container client (%s) from workspace default datastore.", container_name)
            container_client = self.blob_service_client.get_container_client(container_name)

            async with container_client:
                tasks = [
                    self._download_flow_artifacts(httpx_client, container_client, output_asset_id),
                    self._download_snapshot(httpx_client, container_client, snapshot_id),
                ]
                await asyncio.gather(*tasks)

    async def _get_run_data_from_run_history(self, client: httpx.AsyncClient):
        """Get the run data from the run history."""
        logger.debug("Getting run data from run history.")
        headers = self.run_ops._get_headers()
        url = self.run_ops._run_history_endpoint_url + "/rundata"

        payload = {
            "runId": self.run,
            "selectRunMetadata": True,
            "selectRunDefinition": True,
            "selectJobSpecification": True,
        }

        error_msg_prefix = "Failed to get run data from run history"
        try:
            response = await client.post(url, headers=headers, json=payload)
        except Exception as e:
            raise DownloadInternalError(f"{error_msg_prefix}. Error: {e}") from e
        else:
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise RunNotFoundError(f"{error_msg_prefix}. Run {self.run!r} not found.")
            else:
                raise DownloadInternalError(
                    f"{error_msg_prefix}. Code: {response.status_code}. Reason: {response.reason_phrase}"
                )

    def _download_run_metrics(
        self,
    ):
        """Download the run metrics."""
        logger.debug("Downloading run metrics.")
        metrics = self.run_ops.get_metrics(self.run)
        with open(self.output_folder / DownloadedRun.METRICS_FILE_NAME, "w", encoding=DEFAULT_ENCODING) as f:
            json.dump(metrics, f, ensure_ascii=False)
        logger.debug("Downloaded run metrics.")

    async def _download_flow_artifacts(self, httpx_client: httpx.AsyncClient, container_client, output_data):
        """Download the output data."""
        asset_path = await self._get_asset_path(httpx_client, output_data)
        await self._download_blob_folder_from_asset_path(container_client, asset_path)

    async def _download_blob_folder_from_asset_path(
        self, container_client, asset_path: str, local_folder: Optional[Path] = None
    ):
        """Download the blob data from the data path."""
        logger.debug("Downloading all blobs from data path prefix '%s'", asset_path)
        if local_folder is None:
            local_folder = self.output_folder

        tasks = []
        async for blob in container_client.list_blobs(name_starts_with=asset_path):
            blob_client = container_client.get_blob_client(blob.name)
            relative_path = Path(blob.name).relative_to(asset_path)
            local_path = local_folder / relative_path
            tasks.append(self._download_single_blob(blob_client, local_path))
        await asyncio.gather(*tasks)

    async def _download_single_blob(self, blob_client, local_path: Optional[Path] = None):
        """Download a single blob."""
        if local_path is None:
            local_path = Path(self.output_folder / blob_client.blob_name)
        elif local_path.exists():
            raise UserErrorException(f"Local file {local_path.resolve().as_posix()!r} already exists.")

        # ignore some files
        for item in self.IGNORED_PATTERN:
            if item in blob_client.blob_name:
                logger.warning(
                    "Ignoring file '%s' because it matches the ignored pattern '%s'", local_path.as_posix(), item
                )
                return None

        logger.debug("Downloading blob '%s' to local path '%s'", blob_client.blob_name, local_path.resolve().as_posix())
        local_path.parent.mkdir(parents=True, exist_ok=True)
        async with blob_client:
            with open(local_path, "wb") as f:
                stream = await blob_client.download_blob()
                async for chunk in stream.chunks():
                    f.write(chunk)
        return local_path

    async def _download_snapshot(self, httpx_client: httpx.AsyncClient, container_client, snapshot_id):
        """Download the flow snapshot."""
        snapshot_urls = await self._get_flow_snapshot_urls(httpx_client, snapshot_id)

        logger.debug("Downloading all snapshot blobs from snapshot urls.")
        tasks = []
        for url in snapshot_urls:
            blob_name = url.split(self.datastore.container_name)[-1].lstrip("/")
            blob_client = container_client.get_blob_client(blob_name)
            relative_path = url.split(self.run)[-1].lstrip("/")
            local_path = Path(self.output_folder / DownloadedRun.SNAPSHOT_FOLDER / relative_path)
            tasks.append(self._download_single_blob(blob_client, local_path))
        await asyncio.gather(*tasks)

    async def _get_flow_snapshot_urls(self, httpx_client: httpx.AsyncClient, snapshot_id):
        logger.debug("Getting flow snapshot blob urls from snapshot id with calling to content service.")
        headers = self.run_ops._get_headers()
        endpoint = self.run_ops._run_history_endpoint_url.replace("/history/v1.0", "/content/v2.0")
        url = endpoint + "/snapshots/sas"
        payload = {
            "snapshotOrAssetId": snapshot_id,
        }

        error_msg_prefix = (
            f"Failed to download flow snapshots with snapshot id {snapshot_id}, "
            f"because the client failed to retrieve data from content service"
        )
        try:
            response = await httpx_client.post(url, headers=headers, json=payload)
        except Exception as e:
            raise DownloadInternalError(f"{error_msg_prefix}. Error: {e}") from e
        else:
            if response.status_code == 200:
                return self._parse_snapshot_response(response.json())
            elif response.status_code == 404:
                raise DownloadInternalError(f"{error_msg_prefix}. Error: Snapshot id not found.")
            else:
                raise DownloadInternalError(
                    f"{error_msg_prefix}. Code: {response.status_code}. Reason: {response.reason_phrase}"
                )

    async def _get_asset_path(self, client: httpx.AsyncClient, asset_id):
        """Get the asset path from asset id."""
        logger.debug("Getting asset path from asset id with calling to data service.")
        headers = self.run_ops._get_headers()
        endpoint = self.run_ops._run_history_endpoint_url.replace("/history", "/data")
        url = endpoint + "/dataversion/getByAssetId"
        payload = {
            "value": asset_id,
        }

        error_msg_prefix = "Failed to download flow artifacts due to failed to retrieve data from data service"
        try:
            response = await client.post(url, headers=headers, json=payload)
        except Exception as e:
            raise DownloadInternalError(f"{error_msg_prefix}. Error: {e}") from e

        if response.status_code != 200:
            raise DownloadInternalError(
                f"{error_msg_prefix}. Code: {response.status_code}. Reason: {response.reason_phrase}"
            )
        response_data = response.json()
        data_path = response_data["dataVersion"]["dataUri"].split("/paths/")[-1]
        if self._use_flow_outputs:
            data_path = data_path.replace("flow_outputs", "flow_artifacts")
        return data_path

    def _parse_snapshot_response(self, response: dict):
        """Parse the snapshot response."""
        urls = []
        if response["absoluteUrl"]:
            urls.append(response["absoluteUrl"])
        for value in response["children"].values():
            urls += self._parse_snapshot_response(value)

        return urls

    def _download_run_logs(self):
        """Download the run logs."""
        logger.debug("Downloading run logs.")
        logs = self.run_ops._get_log(self.run)

        with open(self.output_folder / DownloadedRun.LOGS_FILE_NAME, "w", encoding=DEFAULT_ENCODING) as f:
            f.write(logs)
        logger.debug("Downloaded run logs.")

    @classmethod
    def _from_run_operations(cls, run_ops: "RunOperations", run: str, output_folder: Union[str, Path]):
        """Create an instance from run operations."""
        from azure.ai.ml.entities._datastore.azure_storage import AzureBlobDatastore

        datastore = run_ops._workspace_default_datastore
        if isinstance(datastore, AzureBlobDatastore):
            return cls(run=run, run_ops=run_ops, output_folder=output_folder)
        else:
            raise UserErrorException(
                f"Cannot download run {run!r} because the workspace default datastore is not supported. Supported ones "
                f"are ['AzureBlobDatastore'], got {type(datastore).__name__!r}."
            )


async def to_thread(func, /, *args, **kwargs):
    # this is copied from asyncio.to_thread() in Python 3.9
    # as it is not available in Python 3.8, which is the minimum supported version of promptflow
    loop = asyncio.get_running_loop()
    ctx = contextvars.copy_context()
    func_call = functools.partial(ctx.run, func, *args, **kwargs)
    return await loop.run_in_executor(None, func_call)
