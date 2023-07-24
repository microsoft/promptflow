# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

import requests

from promptflow.contracts.run_mode import RunMode
from promptflow.utils.dict_utils import get_value_by_key_path

from .utils import FORMATTER, get_logger

logger = get_logger("prt", std_out=True, log_formatter=FORMATTER)


def fill_connection_api_keys(request: dict, connection_file: str) -> dict:
    """fill in the api key for each connection in the request"""
    if not connection_file:
        return

    from promptflow.core.connection_manager import ConnectionManager

    os.environ["PROMPTFLOW_CONNECTIONS"] = connection_file
    connection_manager = ConnectionManager()

    request["connections"] = connection_manager.to_connections_dict()


def _execute(
    input_file,
    url,
    key=None,
    connection_file=None,
    config_file=None,
    output_file="output.json",
    submit_flow_request_file=None,
    workspace_token=None,
    dump_logs=True,
    deployment=None,
):
    """execute a flow file in a exiting promptflow runtime."""
    logger.info("Execute file %s", input_file)
    input_file = Path(input_file).resolve().absolute()
    output_file = Path(output_file).resolve().absolute()

    with open(input_file, "r", encoding="utf-8") as f:
        batch_request = json.load(f)
    fill_connection_api_keys(batch_request, connection_file)

    azure_storage_setting = None
    if config_file:
        azure_storage_setting = get_azure_storage_setting(config_file)

    # additional submit config
    submit_flow_request = {}
    if not submit_flow_request_file:
        sf = Path(str(input_file).replace(".json", ".submit.json"))
        if sf.exists():
            logger.info("Using additional submit config file: %s", sf)
            submit_flow_request_file = sf
    if submit_flow_request_file:
        with open(submit_flow_request_file, "r", encoding="utf-8") as f:
            submit_flow_request = json.load(f)
        logger.info("Additional submit config: %s", submit_flow_request)

    # if workspace_token is None:
    #     from .utils._token_utils import get_default_credential
    #     cred = get_default_credential()
    #     audience = "https://management.azure.com"
    #     workspace_token = cred.get_token(audience).token
    if workspace_token:
        submit_flow_request["workspace_msi_token_for_storage_resource"] = workspace_token

    run_mode = RunMode.BulkTest if batch_request.get("bulk_test_id") else RunMode.Flow
    raw_request = convert_request_to_raw(
        batch_request, run_mode, input_file.stem, submit_flow_request, azure_storage_setting
    )

    flow_id = raw_request["FlowId"]

    client = PromptFlowRuntimeClient(url, key, deployment)
    result = client.submit(raw_request)

    if dump_logs:
        # dump the raw request for diagnostic
        with open(f"{flow_id}_raw.json", "w", encoding="utf-8") as file:
            json.dump(raw_request, file, indent=2)

        # dump the output file for diagnostic
        with open(output_file, "w", encoding="utf-8") as file:
            json.dump(result, file, indent=2)
        logger.info("Saved to %s", output_file)

    return result


def get_azure_storage_setting(config_file):
    """get azure storage setting from config file"""
    from datetime import datetime, timedelta

    from azure.mgmt.storage import StorageManagementClient
    from azure.storage.blob import generate_container_sas
    from azureml.core import Workspace

    from promptflow.contracts.azure_storage_mode import AzureStorageMode

    from .utils._token_utils import get_default_credential

    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)
        ws = Workspace(
            subscription_id=config["subscription_id"],
            resource_group=config["resource_group"],
            workspace_name=config["workspace_name"],
        )

        default_datastore = ws.get_default_datastore()
        storage_account_name = default_datastore.account_name
        blob_container_name = default_datastore.container_name

        credential = get_default_credential()
        storage_client = StorageManagementClient(credential, config["subscription_id"])
        keys = storage_client.storage_accounts.list_keys(config["resource_group"], storage_account_name)
        account_key = keys.keys[0].value

        blob_container_sas_token = generate_container_sas(
            storage_account_name,
            blob_container_name,
            account_key=account_key,
            permission="racwdl",
            expiry=datetime.utcnow() + timedelta(days=1),  # expiry time
        )

        azure_storage_setting = {
            "azure_storage_mode": AzureStorageMode.Blob,
            "storage_account_name": storage_account_name,
            "blob_container_name": blob_container_name,
            "blob_container_sas_token": blob_container_sas_token,
            "output_datastore_name": default_datastore.name,
        }

        return azure_storage_setting


def convert_request_to_raw(
    flow_request,
    run_mode: RunMode,
    source_run_id: str,
    submit_flow_request: dict = {},
    azure_storage_setting: dict = None,
) -> dict:
    """convert a flow request to raw request"""
    flow_run_id = str(uuid.uuid4())
    if not source_run_id:
        source_run_id = str(uuid.uuid4())
    variant_runs = flow_request.get("variants_runs", {})
    if variant_runs:
        flow_request["variants_runs"] = {v: f"{vid}_{flow_run_id}" for v, vid in variant_runs.items()}
    if flow_request.get("eval_flow_run_id"):
        flow_request["eval_flow_run_id"] = f"{flow_request['eval_flow_run_id']}_{flow_run_id}"
    flow_id = get_value_by_key_path(flow_request, "flow/id")

    req = {
        "FlowId": flow_id or str(uuid.uuid4()),
        "FlowRunId": flow_run_id,
        "SourceFlowRunId": source_run_id,
        "SubmissionData": json.dumps(flow_request),
        "RunMode": run_mode.value,
    }

    if azure_storage_setting:
        azure_storage_setting["flow_artifacts_root_path"] = f"promptflow/PromptFlowArtifacts/{flow_run_id}"
        req["AzureStorageSetting"] = azure_storage_setting

    if flow_request.get("flow_source"):
        req["FlowSource"] = flow_request["flow_source"]
        del flow_request["flow_source"]
        req["SubmissionData"] = flow_request

    submit_flow_request.update(**req)
    return submit_flow_request


class PromptFlowRuntimeClient:
    """PromptFlowRuntimeClient is a client to submit a flow to a running promptflow runtime."""

    def __init__(self, url: str, api_key: str = None, deployment: str = None):
        url = url.replace("/submit", "").strip("/")
        self.url = url
        self.timeout = 180
        self.cred = None
        if "instances.azureml.ms" in url or "instances.azureml-test.ms" in url:  # endpoint in compute instance
            from azure.identity import DefaultAzureCredential

            self.cred = DefaultAzureCredential()

        self.api_key = api_key
        self.deployment = deployment

    def get_headers(self):
        """get headers for http request"""
        headers = {}
        token = None
        if self.api_key:
            token = self.api_key

        if self.cred:
            token = self.cred.get_token("https://management.azure.com/.default").token

        if token:
            headers["Authorization"] = "Bearer " + token
        if self.deployment:
            headers["azureml-model-deployment"] = self.deployment

        return headers

    def submit(self, request):
        """submit a flow to a running promptflow runtime."""
        start = datetime.now()
        headers = self.get_headers()
        request_url = f"{self.url}/submit"
        try:
            resp = requests.post(request_url, json=request, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            end = datetime.now()
            result = resp.json()
            logger.info("Http response got 200, from %s, in %s", request_url, end - start)
            return result
        except requests.HTTPError:
            logger.info("Error: %s %s", resp.status_code, resp.text)
            raise

    def meta(self, tool_type, name, payload):
        """get the meta of a flow"""
        resp = requests.post(
            f"{self.url}/meta?tool_type={tool_type}&name={name}",
            json=payload,
            headers=self.get_headers(),
            timeout=self.timeout,
        )
        return resp.json()

    def health(self):
        """check if the runtime is alive"""
        resp = requests.get(f"{self.url}/health", headers=self.get_headers(), timeout=self.timeout)
        return resp.json()


if __name__ == "__main__":
    client = PromptFlowRuntimeClient("http://localhost:8080")
    print(client.health())

    from promptflow.contracts.tool import ToolType

    prompt = """{# This is a answer tool##. #} {# unused #}
You are a chatbot having a conversation with a human.
Given the following extracted parts of a long document and a query, create a final answer with references ("SOURCES").
If you don't know the answer, just say that you don't know. Don't try to make up an answer.
ALWAYS return a "SOURCES" part in your answer.
{{contexts}}
Human: {{query}}"""
    result = client.meta(ToolType.LLM, "answer", prompt)
    print(result)
    dumped_content = json.loads(result)
