# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
import tempfile


def load_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f.readlines()]

def _log_metrics_and_instance_results(metrics, instance_results, tracking_uri, run):
    from mlflow.tracking import MlflowClient
    from promptflow._sdk._configuration import Configuration

    pf_config = Configuration(overrides={
            "trace.destination": tracking_uri
        })

    trace_destination = pf_config.get_trace_destination()

    from promptflow._sdk._tracing import _get_ws_triad_from_pf_config
    from promptflow.azure._cli._utils import _get_azure_pf_client, get_client_for_cli

    ws_triad = _get_ws_triad_from_pf_config(path=run._get_flow_dir().resolve())
    pf_client = _get_azure_pf_client(
        subscription_id=ws_triad.subscription_id,
        resource_group=ws_triad.resource_group_name,
        workspace_name=ws_triad.workspace_name,
    )

    client = MlflowClient(pf_client.ml_client.mlflow_tracking_uri)

    for metric_name, metric_value in metrics.items():
        client.log_metric(run.info.run_id, metric_name, metric_value)

    with tempfile.TemporaryFile(mode="w+") as f:
        instance_results.to_json(f, orient="records", lines=True)
        f.write(json.dumps(instance_result) + "\n")
        client.log_artifact(run.info.run_id, f)
