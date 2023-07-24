import csv
import json
import logging
import os
import re
from pathlib import Path

import yaml
from azure.ai.ml.entities import AzureBlobDatastore
from azure.storage.blob import BlobServiceClient
from utils.run_history_client import RunHistoryClient

from promptflow.storage.azureml_run_storage_v2 import AzureMLRunStorageV2

from .endpoint_client import PromptflowEndpointClient


class BulkRunOutputsValidator:
    def __init__(self, endpoint_client: PromptflowEndpointClient, flow_folder_path, flow_run_id):
        self.endpoint_client = endpoint_client
        self.ml_client = endpoint_client._ml_client
        self.flow_folder_path = flow_folder_path
        self.flow_run_id = flow_run_id
        self.rh_client = RunHistoryClient(self.ml_client)

        # Init the properties
        self._blob_container_client = None
        self._output_files = []
        self._output_files_path = None

    # region properties
    @property
    def blob_container_client(self):
        return self._blob_container_client

    @blob_container_client.setter
    def blob_container_client(self, value):
        self._blob_container_client = value

    @property
    def output_files(self):
        return self._output_files

    @output_files.setter
    def output_files(self, value):
        self._output_files = value

    @property
    def output_files_path(self):
        return self._output_files_path

    @output_files_path.setter
    def output_files_path(self, value):
        self._output_files_path = value

    # endregion

    def assert_output_files(self):
        # Bulk run is async, so wait for completion before validating outputs
        run_data = self.rh_client.wait_for_completion(self.flow_run_id)

        # Get the blob container client and the list of flow output files
        storage_setting = self.endpoint_client.get_azure_storage_setting(self.flow_run_id)
        storage_account_name = storage_setting["storage_account_name"]
        blob_container_name = storage_setting["blob_container_name"]
        flow_artifacts_root_path = storage_setting["flow_artifacts_root_path"]
        output_datastore_name = storage_setting["output_datastore_name"]
        if (
            not storage_account_name
            or not blob_container_name
            or not flow_artifacts_root_path
            or not output_datastore_name
        ):
            raise Exception(f"The storeage setting is invalid: {storage_setting}")

        default_datastore: AzureBlobDatastore = self.ml_client.datastores.get_default()
        default_datastore_name = default_datastore.name
        storage_account_key = self.ml_client.datastores._list_secrets(default_datastore_name).as_dict().get("key", "")
        blob_service_client = BlobServiceClient(
            account_url=f"https://{storage_account_name}.blob.core.windows.net", credential=storage_account_key
        )
        self.blob_container_client = blob_service_client.get_container_client(blob_container_name)
        self.output_files = [
            blob.name for blob in self.blob_container_client.list_blobs(name_starts_with=flow_artifacts_root_path)
        ]
        self.output_files_path = flow_artifacts_root_path

        # Validate the output files
        input_counts = self.get_inputs_count()
        logging.info(f"The bulk run input counts: {input_counts}")
        self.validate_meta()
        self.validate_run_info()
        self.validate_flow_outputs(run_data, output_datastore_name)
        self.validate_flow_artifacts(input_counts)
        self.validate_node_artifacts(input_counts)

    # region validation output files
    def validate_meta(self):
        """Validate the file: meta.json"""
        # Assert meta.json exists
        meta_file = f"{self.output_files_path}/{AzureMLRunStorageV2.META_FILE_NAME}"
        assert meta_file in self.output_files
        # Assert meta.json content is correct
        meta = self.read_json_or_jsonl_from_blob(meta_file)
        assert meta == {"batch_size": 25}
        logging.info("The validation of meta.json is passed.")

    def validate_run_info(self):
        """Validate the file: run_info.json"""
        # Assert run_info.json exists
        run_info_file = f"{self.output_files_path}/run_info.json"
        assert run_info_file in self.output_files
        # Assert run_info.json contains keys: "status", "error", "metrics", "system_metrics"
        run_info = self.read_json_or_jsonl_from_blob(run_info_file)
        assert {"status", "error", "metrics", "system_metrics"}.issubset(run_info.keys())
        logging.info("The validation of run_info.json is passed.")

    def validate_flow_outputs(self, run_data, output_datastore_name):
        """Validate the folder: flow_outputs"""
        # Assert the flow_outputs folder exists
        flow_outputs_folder = f"{self.output_files_path}/{AzureMLRunStorageV2.FLOW_OUTPUTS_FOLDER_NAME}/"
        flow_output_file = flow_outputs_folder + "output.jsonl"
        assert flow_output_file in self.output_files
        # Assert the bulk run has an output asset and point to flow_outputs_folder
        output_data_asset = self.rh_client.get_output_data_asset(run_data)
        data_uri_pattern = r"datastores/([^/]+)/paths/(.*)"
        matches = re.search(data_uri_pattern, output_data_asset.path)
        if matches:
            assert matches.group(1) == output_datastore_name
            assert matches.group(2) == flow_outputs_folder
        else:
            raise Exception(f"Invalid output data asset: {output_data_asset}")
        # We only check output content for python tool test.
        expected_output_path = Path(self.flow_folder_path) / "expected_output.json"
        if expected_output_path.exists():
            expected_output = json.loads(expected_output_path.read_text())
            content = self.read_json_or_jsonl_from_blob(flow_output_file)
            assert content == expected_output, "Expected: {}, Actual: {}".format(expected_output, content)
        logging.info("The validation of flow_outputs is passed.")

    def validate_flow_artifacts(self, input_counts):
        """Validate the folder: flow_artifacts"""
        # Assert the flow_artifacts contains {:09}_{:09}.jsonl file
        flow_artifacts_file = (
            f"{self.output_files_path}/{AzureMLRunStorageV2.FLOW_ARTIFACTS_FOLDER_NAME}/000000000_000000024.jsonl"
        )
        assert flow_artifacts_file in self.output_files
        # Assert each line in the flow_artifacts_file contains keys: "line_number", "run_info"
        flow_artifacts = self.read_json_or_jsonl_from_blob(flow_artifacts_file)
        assert all({"line_number", "run_info"}.issubset(flow_artifact.keys()) for flow_artifact in flow_artifacts)
        # Assert the lines in the flow_artifacts_file should be equal to inputs count
        assert len(flow_artifacts) == input_counts
        logging.info("The validation of flow_artifacts is passed.")
        print("The validation of flow_artifacts is passed.")

    def validate_node_artifacts(self, input_counts):
        """Validate the folder: node_artifacts"""
        # Assert the node_artifacts contains subfolders with node names in the flow and
        # each subfolders contains .jsonl files named {:09}.jsonl
        nodes = []
        with open(self.flow_folder_path / "flow.dag.yaml", "r") as file:
            flow_definition = json.loads(json.dumps(yaml.safe_load(file)))
            nodes = [node.get("name") for node in flow_definition["nodes"]]
        node_artifact_file_list = []
        for node in nodes:
            for i in range(input_counts):
                node_artifact_file_list.append(
                    f"{self.output_files_path}/{AzureMLRunStorageV2.NODE_ARTIFACTS_FOLDER_NAME}/{node}/{i:09d}.jsonl"
                )
        assert set(node_artifact_file_list).issubset(set(self.output_files))
        # Assert each line in the node_artifact_file contains keys: "line_number", "run_info"
        for node_artifact_file in node_artifact_file_list:
            node_artifact = self.read_json_or_jsonl_from_blob(node_artifact_file)
            assert len(node_artifact) == 1
            assert all({"line_number", "run_info"}.issubset(node_artifact.keys()) for node_artifact in node_artifact)
        logging.info("The validation of node_artifacts is passed.")

    # endregion

    # region helper methods
    def get_inputs_count(self):
        data_inputs_path = Path(self.flow_folder_path / "data_inputs.json")
        data_inputs = json.loads(data_inputs_path.read_text())
        # Get the first input file as a refernce
        input_file = Path(self.flow_folder_path / next(iter(data_inputs.values())))
        with open(input_file, "r", newline="") as file:
            csv_reader = csv.reader(file)
            # Skip the first line
            next(csv_reader)
            line_count = sum(1 for _ in csv_reader)
        return line_count

    def read_json_or_jsonl_from_blob(self, blob_file):
        blob_client = self.blob_container_client.get_blob_client(blob=blob_file)
        content = blob_client.download_blob().readall().decode("utf-8")

        file_extension = os.path.splitext(blob_file)[1]
        if file_extension == ".json":
            return json.loads(content)
        elif file_extension == ".jsonl":
            return [json.loads(line) for line in content.splitlines()]
        else:
            raise Exception(f"Unsupported file extension of the output files: {file_extension}")

    # endregion
