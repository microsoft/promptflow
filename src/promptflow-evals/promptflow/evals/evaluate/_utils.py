# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging
import json
import os
import re
import tempfile
from collections import namedtuple
from pathlib import Path

import mlflow

from promptflow._sdk._constants import Local2Cloud
from promptflow._utils.async_utils import async_run_allowing_running_loop
from promptflow.azure.operations._async_run_uploader import AsyncRunUploader

LOGGER = logging.getLogger(__name__)

AZURE_WORKSPACE_REGEX_FORMAT = (
    "^azureml:[/]{1,2}subscriptions/([^/]+)/resource(groups|Groups)/([^/]+)"
    "(/providers/Microsoft.MachineLearningServices)?/workspaces/([^/]+)$"
)

AzureMLWorkspaceTriad = namedtuple("AzureMLWorkspace", ["subscription_id", "resource_group_name", "workspace_name"])


def extract_workspace_triad_from_trace_provider(trace_provider: str):
    match = re.match(AZURE_WORKSPACE_REGEX_FORMAT, trace_provider)
    if not match or len(match.groups()) != 5:
        raise ValueError(
            "Malformed trace provider string, expected azureml://subscriptions/<subscription_id>/"
            "resourceGroups/<resource_group>/providers/Microsoft.MachineLearningServices/"
            f"workspaces/<workspace_name>, got {trace_provider}"
        )
    subscription_id = match.group(1)
    resource_group_name = match.group(3)
    workspace_name = match.group(5)
    return AzureMLWorkspaceTriad(subscription_id, resource_group_name, workspace_name)


def load_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f.readlines()]


def _write_properties_to_run_history(properties: dict) -> None:
    from mlflow.tracking import MlflowClient
    from mlflow.utils.rest_utils import http_request

    # get mlflow run
    run = mlflow.active_run()
    if run is None:
        run = mlflow.start_run()
    # get auth from client
    client = MlflowClient()
    try:
        cred = client._tracking_client.store.get_host_creds()  # pylint: disable=protected-access
        # update host to run history and request PATCH API
        cred.host = cred.host.replace("mlflow/v2.0", "mlflow/v1.0").replace("mlflow/v1.0", "history/v1.0")
        response = http_request(
            host_creds=cred,
            endpoint=f"/experimentids/{run.info.experiment_id}/runs/{run.info.run_id}",
            method="PATCH",
            json={"runId": run.info.run_id, "properties": properties},
        )
        if response.status_code != 200:
            LOGGER.error("Fail writing properties '%s' to run history: %s", properties, response.text)
            response.raise_for_status()
    except AttributeError as e:
        LOGGER.error("Fail writing properties '%s' to run history: %s", properties, e)


def _azure_pf_client(trace_destination):
    from promptflow.azure._cli._utils import _get_azure_pf_client

    ws_triad = extract_workspace_triad_from_trace_provider(trace_destination)
    azure_pf_client = _get_azure_pf_client(
        subscription_id=ws_triad.subscription_id,
        resource_group=ws_triad.resource_group_name,
        workspace_name=ws_triad.workspace_name,
    )

    return azure_pf_client


def _get_mlflow_tracking_uri(trace_destination):
    azure_pf_client = _azure_pf_client(trace_destination)
    ws_triad = extract_workspace_triad_from_trace_provider(trace_destination)

    ws = azure_pf_client.ml_client.workspaces.get(ws_triad.workspace_name)
    return ws.mlflow_tracking_uri


def _get_trace_destination_config(tracking_uri):
    from promptflow._sdk._configuration import Configuration
    pf_config = Configuration(overrides={
        "trace.destination": tracking_uri
    } if tracking_uri is not None else {}
                              )

    trace_destination = pf_config.get_trace_destination()

    return trace_destination


def _log_metrics_and_instance_results(metrics, instance_results, tracking_uri, run, pf_client, data,
                                      evaluation_name=None) -> str:
    run_id = None
    trace_destination = _get_trace_destination_config(tracking_uri=tracking_uri)

    if trace_destination is None:
        return None

    tracking_uri = _get_mlflow_tracking_uri(trace_destination=trace_destination)

    # Adding line_number as index column this is needed by UI to form link to individual instance run
    instance_results["line_number"] = instance_results.index

    if run is None:
        mlflow.set_tracking_uri(tracking_uri)

        with tempfile.TemporaryDirectory() as tmpdir:
            with mlflow.start_run(run_name=evaluation_name) as run:
                tmp_path = os.path.join(tmpdir, "eval_results.jsonl")

                with open(tmp_path, "w", encoding="utf-8") as f:
                    f.write(instance_results.to_json(orient="records", lines=True))

                mlflow.log_artifact(tmp_path)

                # Using mlflow to create a dummy run since once created via PF show traces of dummy run in UI.
                # Those traces can be confusing.
                # adding these properties to avoid showing traces if a dummy run is created
                _write_properties_to_run_history(
                    properties={
                        "_azureml.evaluation_run": "azure-ai-generative-parent",
                        "_azureml.evaluate_artifacts": json.dumps([{"path": "eval_results.jsonl", "type": "table"}])
                    })
                run_id = run.info.run_id
    else:
        azure_pf_client = _azure_pf_client(trace_destination=trace_destination)
        with tempfile.TemporaryDirectory() as temp_dir:
            file_name = Local2Cloud.FLOW_INSTANCE_RESULTS_FILE_NAME
            local_file = Path(temp_dir) / file_name
            instance_results.to_json(local_file, orient="records", lines=True)

            # overriding instance_results.jsonl file
            async_uploader = AsyncRunUploader._from_run_operations(run, azure_pf_client.runs)
            remote_file = (f"{Local2Cloud.BLOB_ROOT_PROMPTFLOW}"
                           f"/{Local2Cloud.BLOB_ARTIFACTS}/{run.name}/{Local2Cloud.FLOW_INSTANCE_RESULTS_FILE_NAME}")
            async_run_allowing_running_loop(async_uploader._upload_local_file_to_blob, local_file, remote_file)
            run_id = run.name

    client = mlflow.tracking.MlflowClient(tracking_uri=tracking_uri)
    for metric_name, metric_value in metrics.items():
        client.log_metric(run_id, metric_name, metric_value)

    return _get_ai_studio_url(trace_destination=trace_destination, evaluation_id=run_id)


def _get_ai_studio_url(trace_destination: str, evaluation_id: str) -> str:
    ws_triad = extract_workspace_triad_from_trace_provider(trace_destination)
    studio_base_url = os.getenv("AI_STUDIO_BASE_URL", "https://ai.azure.com")

    studio_url = f"{studio_base_url}/build/evaluation/{evaluation_id}?wsid=/subscriptions/{ws_triad.subscription_id}" \
                 f"/resourceGroups/{ws_triad.resource_group_name}/providers/Microsoft.MachineLearningServices/" \
                 f"workspaces/{ws_triad.workspace_name}"

    return studio_url
