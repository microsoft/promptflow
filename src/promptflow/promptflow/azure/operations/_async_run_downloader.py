import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Union

import httpx
from azure.storage.blob.aio import BlobServiceClient

from promptflow._sdk._constants import DEFAULT_ENCODING, LOGGER_NAME
from promptflow._sdk._errors import RunNotFoundError, RunOperationError
from promptflow._utils.logger_utils import LoggerFactory
from promptflow.exceptions import UserErrorException

logger = LoggerFactory.get_logger(name=LOGGER_NAME, verbosity=logging.WARNING)


class AsyncRunDownloader:
    """Download run results from the service asynchronously.

    :param run: The run id.
    :type run: str
    :param run_ops: The run operations.
    :type run_ops: ~promptflow.azure.operations.RunOperations
    :param output_folder: The output folder to save the run results.
    :type output_folder: Union[Path, str]
    """

    LOCAL_SNAPSHOT_FOLDER = "snapshot"
    LOCAL_INPUT_FILE_STEM = "inputs"
    LOCAL_METRICS_FILE_NAME = "metrics.json"
    LOCAL_LOGS_FILE_NAME = "logs.txt"

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
        try:
            # pass verify=False to client to disable SSL verification.
            # Source: https://github.com/encode/httpx/issues/1331
            async with httpx.AsyncClient(verify=False) as client:

                async_tasks = [
                    # put async functions in tasks to run in coroutines
                    self._download_run_input_output_and_snapshot(client),
                ]
                sync_tasks = [
                    # below functions are actually synchronous functions in order to reuse code,
                    # the execution time of these functions should be shorter than the above async functions
                    # so it won't increase the total execution time.
                    # the reason we still put them in the tasks is, on one hand the code is more consistent and
                    # we can use asyncio.gather() to wait for all tasks to finish, on the other hand, we can
                    # also evaluate below functions to be shorter than the async functions with the help of logs
                    self._download_run_metrics(),
                    self._download_run_logs(),
                ]
                tasks = async_tasks + sync_tasks
                await asyncio.gather(*tasks)
        except Exception as e:
            raise RunOperationError(f"Failed to download run {self.run!r}. Error: {e}") from e

        return self.output_folder.resolve().as_posix()

    async def _download_run_input_output_and_snapshot(self, httpx_client: httpx.AsyncClient):
        run_data = await self._get_run_data_from_run_history(httpx_client)

        logger.debug("Parsing run data from run history to get necessary information.")
        # extract necessary information from run data
        snapshot_id = run_data["runMetadata"]["properties"]["azureml.promptflow.snapshot_id"]
        input_data_path = run_data["runMetadata"]["properties"]["azureml.promptflow.input_data"]
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

        async with self.blob_service_client:
            container_name = self.datastore.container_name
            logger.debug("Getting container client (%s) from workspace default datastore.", container_name)
            container_client = self.blob_service_client.get_container_client(container_name)

            async with container_client:
                tasks = [
                    self._download_input_data(container_client, input_data_path),
                    self._download_output_data(httpx_client, container_client, output_asset_id),
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

        response = await client.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            raise RunNotFoundError(f"Run {self.run!r} not found.")
        else:
            raise RunOperationError(
                f"Failed to get run from service. Code: {response.status_code}, text: {response.text}"
            )

    async def _download_run_metrics(
        self,
    ):
        """Download the run metrics."""
        logger.debug("Downloading run metrics.")
        metrics = self.run_ops.get_metrics(self.run)
        with open(self.output_folder / self.LOCAL_METRICS_FILE_NAME, "w", encoding=DEFAULT_ENCODING) as f:
            json.dump(metrics, f, ensure_ascii=False)
        logger.debug("Downloaded run metrics.")

    async def _download_input_data(self, container_client, input_data):
        """Download the input data."""
        logger.debug("Getting input data with container client.")
        input_path = input_data.split("/paths/")[-1]
        original_path = Path(input_path)
        # rename the input data to "inputs.<ext>" when downloading to local
        local_path = Path(self.output_folder / f"{self.LOCAL_INPUT_FILE_STEM}{original_path.suffix}")
        blob_client = container_client.get_blob_client(input_path)
        await self._download_single_blob(blob_client, local_path)

    async def _download_output_data(self, httpx_client: httpx.AsyncClient, container_client, output_data):
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
                data = await stream.readall()
                # TODO: File IO may block the event loop, consider using thread pool. e.g. to_thread() method
                f.write(data)
        return local_path

    async def _download_snapshot(self, httpx_client: httpx.AsyncClient, container_client, snapshot_id):
        """Download the flow snapshot."""
        snapshot_urls = await self._get_flow_snapshot_sas_token(httpx_client, snapshot_id)

        logger.debug("Downloading all snapshot blobs from snapshot urls.")
        tasks = []
        for url in snapshot_urls:
            blob_name = url.split(self.datastore.container_name)[-1].lstrip("/")
            blob_client = container_client.get_blob_client(blob_name)
            relative_path = url.split(self.run)[-1].lstrip("/")
            local_path = Path(self.output_folder / self.LOCAL_SNAPSHOT_FOLDER / relative_path)
            tasks.append(self._download_single_blob(blob_client, local_path))
        await asyncio.gather(*tasks)

    async def _get_flow_snapshot_sas_token(self, httpx_client: httpx.AsyncClient, snapshot_id):
        logger.debug("Getting flow snapshot blob urls from snapshot id with calling to content service.")
        headers = self.run_ops._get_headers()
        endpoint = self.run_ops._run_history_endpoint_url.replace("/history/v1.0", "/content/v2.0")
        url = endpoint + "/snapshots/sas"
        payload = {
            "snapshotOrAssetId": snapshot_id,
        }

        response = await httpx_client.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            return self._parse_snapshot_response(response.json())
        elif response.status_code == 404:
            raise UserErrorException(f"Snapshot {snapshot_id!r} not found.")
        else:
            raise RunOperationError(
                f"Failed to get snapshot {snapshot_id!r} from content service. "
                f"Code: {response.status_code}, text: {response.text}"
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

        response = await client.post(url, headers=headers, json=payload)
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

    async def _download_run_logs(self):
        """Download the run logs."""
        logger.debug("Downloading run logs.")
        logs = self.run_ops._get_log(self.run)

        with open(self.output_folder / self.LOCAL_LOGS_FILE_NAME, "w", encoding=DEFAULT_ENCODING) as f:
            f.write(logs)
        logger.debug("Downloaded run logs.")
