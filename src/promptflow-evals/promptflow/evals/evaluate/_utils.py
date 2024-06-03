# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
import logging
import os
import re
import tempfile
from collections import namedtuple
from pathlib import Path

import mlflow
import pandas as pd

from promptflow._sdk._constants import Local2Cloud
from promptflow._utils.async_utils import async_run_allowing_running_loop
from promptflow.azure._dependencies._pf_evals import AsyncRunUploader
from promptflow.evals._constants import DEFAULT_EVALUATION_RESULTS_FILE_NAME, Prefixes

LOGGER = logging.getLogger(__name__)

AZURE_WORKSPACE_REGEX_FORMAT = (
    "^azureml:[/]{1,2}subscriptions/([^/]+)/resource(groups|Groups)/([^/]+)"
    "(/providers/Microsoft.MachineLearningServices)?/workspaces/([^/]+)$"
)

AzureMLWorkspaceTriad = namedtuple("AzureMLWorkspace", ["subscription_id", "resource_group_name", "workspace_name"])


def is_none(value):
    return value is None or str(value).lower() == "none"


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

    pf_config = Configuration(overrides={"trace.destination": tracking_uri} if tracking_uri is not None else None)

    trace_destination = pf_config.get_trace_destination()

    if is_none(trace_destination):
        return None

    return trace_destination


def _log_metrics_and_instance_results(
    metrics, instance_results, tracking_uri, run, pf_client, data, evaluation_name=None
) -> str:
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
                        "_azureml.evaluate_artifacts": json.dumps([{"path": "eval_results.jsonl", "type": "table"}]),
                        "isEvaluatorRun": "true",
                    }
                )
                run_id = run.info.run_id
    else:
        azure_pf_client = _azure_pf_client(trace_destination=trace_destination)
        with tempfile.TemporaryDirectory() as temp_dir:
            file_name = Local2Cloud.FLOW_INSTANCE_RESULTS_FILE_NAME
            local_file = Path(temp_dir) / file_name
            instance_results.to_json(local_file, orient="records", lines=True)

            # overriding instance_results.jsonl file
            async_uploader = AsyncRunUploader._from_run_operations(azure_pf_client.runs)
            remote_file = (
                f"{Local2Cloud.BLOB_ROOT_PROMPTFLOW}"
                f"/{Local2Cloud.BLOB_ARTIFACTS}/{run.name}/{Local2Cloud.FLOW_INSTANCE_RESULTS_FILE_NAME}"
            )
            async_run_allowing_running_loop(async_uploader._upload_local_file_to_blob, local_file, remote_file)
            run_id = run.name

    client = mlflow.tracking.MlflowClient(tracking_uri=tracking_uri)
    for metric_name, metric_value in metrics.items():
        client.log_metric(run_id, metric_name, metric_value)

    return _get_ai_studio_url(trace_destination=trace_destination, evaluation_id=run_id)


def _get_ai_studio_url(trace_destination: str, evaluation_id: str) -> str:
    ws_triad = extract_workspace_triad_from_trace_provider(trace_destination)
    studio_base_url = os.getenv("AI_STUDIO_BASE_URL", "https://ai.azure.com")

    studio_url = (
        f"{studio_base_url}/build/evaluation/{evaluation_id}?wsid=/subscriptions/{ws_triad.subscription_id}"
        f"/resourceGroups/{ws_triad.resource_group_name}/providers/Microsoft.MachineLearningServices/"
        f"workspaces/{ws_triad.workspace_name}"
    )

    return studio_url


def _trace_destination_from_project_scope(project_scope: dict) -> str:
    subscription_id = project_scope["subscription_id"]
    resource_group_name = project_scope["resource_group_name"]
    workspace_name = project_scope["project_name"]

    trace_destination = (
        f"azureml://subscriptions/{subscription_id}/resourceGroups/{resource_group_name}/"
        f"providers/Microsoft.MachineLearningServices/workspaces/{workspace_name}"
    )

    return trace_destination


def _write_output(path, data_dict):
    p = Path(path)
    if os.path.isdir(path):
        p = p / DEFAULT_EVALUATION_RESULTS_FILE_NAME

    with open(p, "w") as f:
        json.dump(data_dict, f)


def _apply_column_mapping(source_df: pd.DataFrame, mapping_config: dict, inplace: bool = False) -> pd.DataFrame:
    """
    Apply column mapping to source_df based on mapping_config.

    This function is used for pre-validation of input data for evaluators
    :param source_df: the data frame to be changed.
    :type source_df: pd.DataFrame
    :param mapping_config: The configuration, containing column mapping.
    :type mapping_config: dict.
    :param inplace: If true, the source_df will be changed inplace.
    :type inplace: bool
    :return: The modified data frame.
    """
    result_df = source_df

    if mapping_config:
        column_mapping = {}
        columns_to_drop = set()
        pattern_prefix = "data."
        run_outputs_prefix = "run.outputs."

        for map_to_key, map_value in mapping_config.items():
            match = re.search(r"^\${([^{}]+)}$", map_value)
            if match is not None:
                pattern = match.group(1)
                if pattern.startswith(pattern_prefix):
                    map_from_key = pattern[len(pattern_prefix) :]
                elif pattern.startswith(run_outputs_prefix):
                    # Target-generated columns always starts from .outputs.
                    map_from_key = f"{Prefixes._TGT_OUTPUTS}{pattern[len(run_outputs_prefix) :]}"
                # if we are not renaming anything, skip.
                if map_from_key == map_to_key:
                    continue
                # If column needs to be mapped to already existing column, we will add it
                # to the drop list.
                if map_to_key in source_df.columns:
                    columns_to_drop.add(map_to_key)
                column_mapping[map_from_key] = map_to_key
        # If we map column to another one, which is already present in the data
        # set and the letter also needs to be mapped, we will not drop it, but map
        # instead.
        columns_to_drop = columns_to_drop - set(column_mapping.keys())
        result_df = source_df.drop(columns=columns_to_drop, inplace=inplace)
        result_df.rename(columns=column_mapping, inplace=True)

    return result_df
