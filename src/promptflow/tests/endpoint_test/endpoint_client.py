import json
import logging
import os
import socket
import uuid
from datetime import datetime, timedelta
from functools import cached_property
from pathlib import Path

import requests
from azure.ai.ml import MLClient
from azure.ai.ml.constants import AssetTypes
from azure.ai.ml.entities import AzureBlobDatastore, Data
from azure.storage.blob import generate_container_sas
from azure.storage.fileshare import AccountSasPermissions, ResourceTypes, generate_account_sas
from azureml._restclient.snapshots_client import SnapshotsClient
from azureml.core import Workspace

import promptflow.azure as pf
from promptflow.azure._load_functions import load_flow
from promptflow.azure.operations import FlowOperations
from promptflow.contracts.azure_storage_mode import AzureStorageMode
from promptflow.contracts.runtime import (
    AzureFileShareInfo,
    FlowSource,
    FlowSourceType,
    SnapshotInfo,
    SubmissionRequestBaseV2,
)
from promptflow.core.connection_manager import ConnectionManager
from promptflow.utils.dataclass_serializer import serialize

DEFAULT_FILESHARE_DATASTORE = "workspaceworkingdirectory"
LOCAL_DEBUG_PORT = 5000


class PromptflowEndpointClient:
    """A client class that can send requests to endpoint to submit flows."""

    def __init__(self, execute_config: dict, ml_client: MLClient):
        self._ml_client = ml_client
        self._fileshare_datastore = ml_client.datastores.get(DEFAULT_FILESHARE_DATASTORE)._to_dict()
        self._fileshare_account_key = ml_client.datastores._list_secrets(DEFAULT_FILESHARE_DATASTORE).as_dict()

        self._endpoint_url = execute_config.get("endpoint_url")
        self._endpoint_key = execute_config.get("endpoint_key")
        self._deployment_name = execute_config.get("deployment_name")
        self._connection_file = execute_config.get("connection_file_path")

    @cached_property
    def base_url(self):
        if self.is_running_in_local:
            return f"http://127.0.0.1:{LOCAL_DEBUG_PORT}"
        return self._endpoint_url

    @cached_property
    def headers(self):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._endpoint_key}",
        }
        if self._deployment_name:
            headers["azureml-model-deployment"] = self._deployment_name
        return headers

    @cached_property
    def connections(self):
        """get connection api keys"""
        os.environ["PROMPTFLOW_CONNECTIONS"] = self._connection_file
        return ConnectionManager().to_connections_dict()

    @cached_property
    def fileshare_sas_token(self):
        return generate_account_sas(
            account_name=self._fileshare_datastore.get("account_name", ""),
            account_key=self._fileshare_account_key.get("key", ""),
            resource_types=ResourceTypes(container=True, object=True),
            permission=AccountSasPermissions(read=True, list=True),
            expiry=datetime.utcnow() + timedelta(hours=2),
        )

    @property
    def is_running_in_local(self):
        # If you want to run tests locally, you can add the below config to .vscode/launch.json and start debugging.
        """
        {
            "name": "Python: Local Run",
            "type": "python",
            "request": "launch",
            "module": "flask",
            "env": {
                "FLASK_APP": "src/promptflow-sdk/promptflow/runtime/app.py",
                "FLASK_DEBUG": "1"
            },
            "args": [
                "run",
                "--no-debugger",
                "--no-reload",
                "--port",
                "5000"
            ],
            "jinja": true,
            "justMyCode": true
        }
        """
        try:
            socket.create_connection(("localhost", LOCAL_DEBUG_PORT), timeout=1)
            return True
        except (ConnectionRefusedError, TimeoutError, socket.timeout):
            return False

    # region submit flow
    def submit_flow(self, flow_folder_path, env_vars=None):
        # Upload flow to file share
        flow = self.upload_flow_to_file_share(flow_folder_path)
        # Construct submission payload
        flow_run_id = str(uuid.uuid4())
        payload = self.prepare_base_submission_payload(flow_run_id, flow=flow, env_vars=env_vars)

        input_path = Path(flow_folder_path / "inputs.json")
        if input_path.exists():
            flow_inputs = json.loads(input_path.read_text())
            if isinstance(flow_inputs, list) and len(flow_inputs) > 0:
                flow_inputs = flow_inputs[0]
            payload["inputs"] = flow_inputs
        else:
            raise ValueError("Failed to find data_inputs.json in flow folder.")
        # Send request to endpoint
        response = self.post(relative_path="submit_flow", payload=payload)
        # Parse response
        return response

    def submit_bulk_run(self, flow_folder_path):
        # Upload flow to snapshot
        snapshot_id = self.upload_flow_to_snapshot(flow_folder_path)
        # Construct submission payload
        flow_run_id = str(uuid.uuid4())
        payload = self.prepare_base_submission_payload(flow_run_id, snapshot_id=snapshot_id)
        payload["azure_storage_setting"] = self.get_azure_storage_setting(flow_run_id)

        data_inputs_path = Path(flow_folder_path / "data_inputs.json")
        if data_inputs_path.exists():
            data_inputs = json.loads(data_inputs_path.read_text())
            payload["data_inputs"] = {
                name: self.create_and_get_data_uri(flow_folder_path, data_file)
                for name, data_file in data_inputs.items()
            }
        else:
            raise ValueError("Failed to find data_inputs.json in flow folder.")

        inputs_mapping_path = Path(flow_folder_path / "inputs_mapping.json")
        if inputs_mapping_path.exists():
            payload["inputs_mapping"] = json.loads(inputs_mapping_path.read_text())
        # Send request to endpoint
        self.post(relative_path="submit_bulk_run", payload=payload)
        return flow_run_id

    def post(self, relative_path, payload):
        start = datetime.now()
        request_url = f"{self.base_url}/{relative_path}"
        try:
            resp = requests.post(request_url, json=payload, headers=self.headers)
            resp.raise_for_status()
            end = datetime.now()
            result = resp.json()
            logging.info("Http response got 200, from %s, in %s", request_url, end - start)
            return result
        except requests.HTTPError:
            logging.info(f"Failed to send request to {request_url} due to {resp.text} ({resp.status_code}).")
            raise

    # endregion

    # region upload flow
    def upload_flow_to_file_share(self, flow_folder_path):
        """Upload a flow to file share and return the flow object."""
        pf.configure(client=self._ml_client)
        flow = load_flow(source=flow_folder_path)
        flow_operations = FlowOperations(
            operation_scope=self._ml_client._operation_scope,
            operation_config=self._ml_client._operation_config,
            all_operations=self._ml_client._operation_container,
            credential=self._ml_client._credential,
        )
        flow_operations._resolve_arm_id_or_upload_dependencies(flow)
        if not flow.path:
            raise ValueError("Failed to upload flow to file share. Please check the local flow path.")
        logging.info(f"Uploaded flow to fileshare: {flow.path}")
        return flow

    def upload_flow_to_snapshot(self, folder_path):
        workspace = Workspace.get(
            name=self._ml_client.workspace_name,
            subscription_id=self._ml_client.subscription_id,
            resource_group=self._ml_client.resource_group_name,
        )
        snapshot_client = SnapshotsClient(workspace.service_context)
        return snapshot_client.create_snapshot(folder_path)

    # endregion

    # region prepare pyload
    def prepare_base_submission_payload(self, flow_run_id, flow=None, snapshot_id=None, env_vars=None):
        flow_path = flow.path if flow else None
        flow_request = SubmissionRequestBaseV2(
            flow_id=str(uuid.uuid4()),
            flow_run_id=flow_run_id,
            connections=self.connections,
            flow_source=self.prepare_flow_source(flow_path, snapshot_id),
            environment_variables=env_vars,
        )
        return serialize(flow_request)

    def prepare_flow_source(self, flow_path=None, snapshot_id=None):
        if flow_path:
            working_dir = os.path.dirname(flow_path)
            flow_dag_file = os.path.basename(flow_path)
            return FlowSource(
                flow_source_type=FlowSourceType.AzureFileShare,
                flow_source_info=AzureFileShareInfo(working_dir=working_dir, sas_url=self.get_sas_url(working_dir)),
                flow_dag_file=flow_dag_file,
            )
        elif snapshot_id:
            return FlowSource(
                flow_source_type=FlowSourceType.Snapshot,
                flow_source_info=SnapshotInfo(snapshot_id=snapshot_id),
                flow_dag_file="flow.dag.yaml",
            )
        else:
            raise ValueError("Either flow_path or snapshot_id should be provided.")

    def get_sas_url(self, flow_path):
        account_name = self._fileshare_datastore.get("account_name", "")
        fileshare_name = self._fileshare_datastore.get("file_share_name", "")
        return f"https://{account_name}.file.core.windows.net/{fileshare_name}/{flow_path}/*?{self.fileshare_sas_token}"

    def get_azure_storage_setting(self, flow_run_id):
        # Get default datastore info
        default_datastore: AzureBlobDatastore = self._ml_client.datastores.get_default()
        default_datastore_name = default_datastore.name
        blob_container_name = default_datastore.container_name
        storage_account_name = default_datastore.account_name
        storage_account_key = self._ml_client.datastores._list_secrets(default_datastore_name).as_dict().get("key", "")
        blob_container_sas_token = generate_container_sas(
            account_name=storage_account_name,
            container_name=blob_container_name,
            account_key=storage_account_key,
            permission="racwdl",
            expiry=datetime.utcnow() + timedelta(days=1),
        )

        # Construct azure storage setting
        azure_storage_setting = {
            "azure_storage_mode": AzureStorageMode.Blob,
            "storage_account_name": storage_account_name,
            "blob_container_name": blob_container_name,
            "blob_container_sas_token": blob_container_sas_token,
            "output_datastore_name": default_datastore_name,
            "flow_artifacts_root_path": f"promptflow/PromptFlowArtifacts/{flow_run_id}",
        }
        return azure_storage_setting

    def get_data_uri(self, data_name, version="1"):
        data_path = self._ml_client.data.get(data_name, version)._to_dict().get("path", None)
        if not data_path:
            raise ValueError(f"Data {data_name} with version {version} does not exist.")
        return data_path

    def create_and_get_data_uri(self, flow_folder_path, file_name):
        file_path = flow_folder_path / file_name
        data = Data(
            path=file_path,
            type=AssetTypes.URI_FILE,
            description="For endpoint testing",
            name=f"endpoint_test_{os.path.splitext(file_name)[0]}",
        )
        data_asset = self._ml_client.data.create_or_update(data)
        return data_asset.path

    # endregion
