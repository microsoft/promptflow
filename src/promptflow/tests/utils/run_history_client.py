import json
import logging
import time
from datetime import datetime, timedelta
from functools import cached_property

import requests
from azure.ai.ml import MLClient

from promptflow.utils.dict_utils import get_value_by_key_path
from promptflow.utils.str_utils import convert_to_dictionary, remove_prefix


class RunHistoryClient:
    def __init__(self, ml_client: MLClient):
        self.ml_client = ml_client
        self.workspace = ml_client.workspaces.get()

    @cached_property
    def api_host(self):
        resp = requests.get(self.workspace.discovery_url, headers=self.headers)
        return resp.json().get("api")

    @cached_property
    def base_url(self):
        return f"{self.api_host}/history/v1.0{self.workspace.id}"

    @cached_property
    def headers(self):
        token = self.ml_client._credential.get_token("https://management.azure.com/.default")
        return {"Authorization": f"Bearer {token.token}"}

    def wait_for_completion(self, run_id, timeout=timedelta(seconds=100)):
        start = datetime.now()
        run_status = "NotStarted"
        while run_status not in ["Completed", "Failed", "Canceled"]:
            if datetime.now() - start > timeout:
                raise Exception(f"The run {run_id} did not complete in 100 seconds")
            # Intermittently get run data to reduce API calls.
            time.sleep(2)
            run_status = self.get_run_status(run_id)
        duration = datetime.now() - start
        if run_status != "Completed":
            raise Exception(f"The run {run_id} failed with status {run_status} in {duration}")
        run_data = self.get_run_data(run_id)
        logging.info(f"The run {run_id} completed in {duration}, run data:\n{json.dumps(run_data, indent=4)}")
        print(f"The run {run_id} completed in {duration}")
        return run_data

    def get_run_data(self, run_id):
        payload = {"runId": run_id, "selectRunMetadata": True}
        response = self.post(relative_path="rundata", payload=payload)
        return response.get("runMetadata", {})

    def get_run_status(self, run_id):
        run_data = self.get_run_data(run_id)
        return run_data.get("status", "Unknown")

    def get_output_data_asset(self, run_data):
        output_asset_id = get_value_by_key_path(run_data, "outputs/flow_outputs/assetId")
        if not output_asset_id:
            raise Exception("No output asset id found in run data")
        logging.info(f"The output asset id: {output_asset_id}")
        output_asset = convert_to_dictionary(remove_prefix(output_asset_id, "azureml://"))
        return self.ml_client.data.get(output_asset["data"], output_asset["versions"])

    def post(self, relative_path, payload):
        request_url = f"{self.base_url}/{relative_path}"
        start = datetime.now()
        try:
            resp = requests.post(url=request_url, json=payload, headers=self.headers)
            resp.raise_for_status()
            end = datetime.now()
            result = resp.json()
            logging.info("Http response got 200, from %s, in %s", request_url, end - start)
            return result
        except requests.HTTPError:
            logging.info(f"Failed to send request to {request_url} due to {resp.text} ({resp.status_code}).")
            raise
