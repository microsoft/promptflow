import asyncio
import logging
from pathlib import Path
from typing import Optional, Union

import httpx
from azure.storage.blob.aio import BlobServiceClient

from promptflow._sdk._constants import LOGGER_NAME
from promptflow._sdk._errors import RunNotFoundError, RunOperationError
from promptflow._utils.logger_utils import LoggerFactory
from promptflow.exceptions import UserErrorException

logger = LoggerFactory.get_logger(name=LOGGER_NAME, verbosity=logging.WARNING)


class RunDownloader:
    """Download run results from the service asynchronously.

    :param run: The run id.
    :type run: str
    :param run_ops: The run operations.
    :type run_ops: ~promptflow.azure.operations.RunOperations
    :param output_folder: The output folder to save the run results.
    :type output_folder: Union[Path, str]
    """

    def __init__(self, run: str, run_ops: "RunOperations", output_folder: Union[str, Path]) -> None:
        self.run = run
        self.run_ops = run_ops
        self.datastore = run_ops._workspace_default_datastore
        self.output_folder = Path(output_folder)
        self.blob_service_client = self._init_blob_service_client()
        self._use_flow_outputs = False  # old runtime does not write debug_info output asset, use flow_outputs instead

    def _init_blob_service_client(self):
        account_url = f"{self.datastore.account_name}.blob.{self.datastore.endpoint}"
        return BlobServiceClient(account_url=account_url, credential=self.run_ops._credential)

    async def download(self) -> str:
        """Download the run results asynchronously."""
        try:
            # pass verify=False to client to disable SSL verification.
            # Source: https://github.com/encode/httpx/issues/1331
            async with httpx.AsyncClient(verify=False) as client:
                tasks = [
                    self._download_run_input_output_and_snapshot(client),
                    self._download_run_metrics(client),
                ]
                await asyncio.gather(*tasks)
        except Exception as e:
            raise RunOperationError(f"Failed to download run {self.run!r}. Error: {e}") from e

        return Path(self.output_folder / self.run).resolve().as_posix()

    async def _download_run_input_output_and_snapshot(self, httpx_client: httpx.AsyncClient):
        run_data = await self._get_run_data_from_run_history(httpx_client)

        # extract necessary information from run data
        flow_resource_id = run_data["runMetadata"]["properties"]["azureml.promptflow.flow_definition_resource_id"]
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
            container_client = self.blob_service_client.get_container_client(self.datastore.container_name)

            async with container_client:
                tasks = [
                    self._download_input_data(container_client, input_data_path),
                    self._download_output_data(httpx_client, container_client, output_asset_id),
                    self._download_snapshot(httpx_client, container_client, flow_resource_id),
                ]
                await asyncio.gather(*tasks)

    async def _get_run_data_from_run_history(self, client: httpx.AsyncClient):
        """Get the run data from the run history."""
        headers = self.run_ops._get_headers()
        url = self.run_ops._run_history_endpoint_url + "/rundata"

        payload = {
            "runId": self.run,
            "selectRunMetadata": True,
            "selectRunDefinition": True,
            "selectJobSpecification": True,
        }

        try:
            response = await client.post(url, headers=headers, json=payload)
        except Exception as e:
            raise RunOperationError(f"Failed to get run from service. Error: {e}") from e
        else:
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise RunNotFoundError(f"Run {self.run!r} not found.")
            else:
                raise RunOperationError(
                    f"Failed to get run from service. Code: {response.status_code}, text: {response.text}"
                )

    async def _download_run_metrics(self, client: httpx.AsyncClient):
        """Download the run metrics."""
        pass

    async def _download_input_data(self, container_client, input_data):
        """Download the input data."""
        input_path = input_data.split("/paths/")[-1]
        original_path = Path(input_path)
        # rename the input data to "inputs.<ext>" when downloading to local
        local_path = Path(self.output_folder / self.run / f"inputs.{original_path.suffix}")
        blob_client = container_client.get_blob_client(input_path)
        await self._download_single_blob(blob_client, local_path)

    async def _download_output_data(self, httpx_client: httpx.AsyncClient, container_client, output_data):
        """Download the output data."""
        asset_path = await self._get_asset_path(httpx_client, output_data)
        await self._download_blob_data_from_data_path(container_client, asset_path)

    async def _download_blob_data_from_data_path(self, container_client, asset_path: str):
        """Download the blob data from the data path."""
        tasks = []
        async for blob in container_client.list_blobs(name_starts_with=asset_path):
            blob_client = container_client.get_blob_client(blob.name)
            local_path = Path(self.output_folder / self.run / blob_client.blob_name)
            tasks.append(self._download_single_blob(blob_client, local_path))
        await asyncio.gather(*tasks)

    async def _download_single_blob(self, blob_client, local_path: Optional[Path] = None):
        """Download a single blob."""
        if local_path is None:
            local_path = Path(self.output_folder / self.run / blob_client.blob_name)
        elif local_path.exists():
            raise UserErrorException(f"Local file {local_path.resolve().as_posix()!r} already exists.")
        local_path.parent.mkdir(parents=True, exist_ok=True)
        async with blob_client:
            with open(local_path, "wb") as f:
                stream = await blob_client.download_blob()
                data = await stream.readall()
                # TODO: File IO may block the event loop, consider using to_thread method
                f.write(data)
        return local_path

    async def _download_snapshot(self, client: httpx.AsyncClient, container_client, flow_resource_id):
        """Download the flow snapshot."""
        pass

    async def _get_asset_path(self, client: httpx.AsyncClient, asset_id):
        """Get the asset path from asset id."""
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
