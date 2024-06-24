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

import pandas as pd

from promptflow.evals._constants import DEFAULT_EVALUATION_RESULTS_FILE_NAME, Prefixes
from promptflow.evals.evaluate._eval_run import EvalRun


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
    run = EvalRun.get_instance()
    try:
        # update host to run history and request PATCH API
        response = run.request_with_retry(
            url=run.get_run_history_uri(),
            method="PATCH",
            json_dict={"runId": run.info.run_id, "properties": properties},
        )
        if response.status_code != 200:
            LOGGER.error("Fail writing properties '%s' to run history: %s", properties, response.text)
            response.raise_for_status()
    except AttributeError as e:
        LOGGER.error("Fail writing properties '%s' to run history: %s", properties, e)


def _azure_pf_client_and_triad(trace_destination):
    from promptflow.azure._cli._utils import _get_azure_pf_client

    ws_triad = extract_workspace_triad_from_trace_provider(trace_destination)
    azure_pf_client = _get_azure_pf_client(
        subscription_id=ws_triad.subscription_id,
        resource_group=ws_triad.resource_group_name,
        workspace_name=ws_triad.workspace_name,
    )

    return azure_pf_client, ws_triad


def _log_metrics_and_instance_results(
    metrics, instance_results, trace_destination, run, evaluation_name,
) -> str:
    if trace_destination is None:
        LOGGER.error("Unable to log traces as trace destination was not defined.")
        return None

    azure_pf_client, ws_triad = _azure_pf_client_and_triad(trace_destination)
    tracking_uri = azure_pf_client.ml_client.workspaces.get(ws_triad.workspace_name).mlflow_tracking_uri

    # Adding line_number as index column this is needed by UI to form link to individual instance run
    instance_results["line_number"] = instance_results.index.values

    ev_run = EvalRun(
        run_name=run.name if run is not None else evaluation_name,
        tracking_uri=tracking_uri,
        subscription_id=ws_triad.subscription_id,
        group_name=ws_triad.resource_group_name,
        workspace_name=ws_triad.workspace_name,
        ml_client=azure_pf_client.ml_client,
        promptflow_run=run,
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = os.path.join(tmpdir, EvalRun.EVALUATION_ARTIFACT)

        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(instance_results.to_json(orient="records", lines=True))

        ev_run.log_artifact(tmpdir)

        # Using mlflow to create a dummy run since once created via PF show traces of dummy run in UI.
        # Those traces can be confusing.
        # adding these properties to avoid showing traces if a dummy run is created.
        # We are doing that only for the pure evaluation runs.
        if run is None:
            _write_properties_to_run_history(
                properties={
                    "_azureml.evaluation_run": "promptflow.BatchRun",
                    "_azureml.evaluate_artifacts": json.dumps([{"path": EvalRun.EVALUATION_ARTIFACT, "type": "table"}]),
                    "isEvaluatorRun": "true",
                    "runType": "eval_run",
                }
            )

    for metric_name, metric_value in metrics.items():
        ev_run.log_metric(metric_name, metric_value)

    ev_run.end_run("FINISHED")
    evaluation_id = ev_run.info.run_name if run is not None else ev_run.info.run_id
    return _get_ai_studio_url(trace_destination=trace_destination, evaluation_id=evaluation_id)


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
                    map_from_key = pattern[len(pattern_prefix):]
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


def _has_aggregator(evaluator):
    return hasattr(evaluator, "__aggregate__")
