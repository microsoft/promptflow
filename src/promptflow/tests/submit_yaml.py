import argparse
import json
import uuid
from pathlib import Path
import requests
from tempfile import mkdtemp
from promptflow.contracts.runtime import SubmissionRequestBaseV2, FlowSource, FlowSourceType, AzureFileShareInfo
from promptflow.utils.dataclass_serializer import serialize


def prepare_flow_source(flow_dag_file, working_dir="", sas_url=None):
    return FlowSource(
        FlowSourceType.AzureFileShare,
        AzureFileShareInfo(working_dir=working_dir, sas_url=sas_url),
        flow_dag_file,
    )


def prepare_base_submission_payload(flow_dag_file, working_dir="", sas_url=None, is_local=False):
    dummy_id = str(uuid.uuid4())
    log_path = Path(mkdtemp()) / f"{dummy_id}.txt" if is_local else f"/tmp/{dummy_id}.txt"
    flow_request = SubmissionRequestBaseV2(
        flow_id=dummy_id,
        flow_run_id=dummy_id,
        flow_source=prepare_flow_source(flow_dag_file, working_dir, sas_url),
        connections={},
        log_path=str(log_path),

    )
    print(f"The log will be written in '{log_path}'")
    return serialize(flow_request)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--flow", "-f", type=str, required=True)
    parser.add_argument("--sas")
    parser.add_argument("--host", default="http://127.0.0.1:5000")
    parser.add_argument("--deployment")
    parser.add_argument("--api_key")
    parser.add_argument("--inputs", "-i", type=str)
    args = parser.parse_args()
    flow_url = args.host + "/submit_flow"
    is_local = args.host.startswith("http://127")
    if args.sas:
        req = prepare_base_submission_payload(args.flow, sas_url=args.sas, is_local=is_local)
    else:
        path = Path(args.flow)
        req = prepare_base_submission_payload(path.name, working_dir=str(path.parent), is_local=is_local)
    if args.inputs is None:
        args.inputs = Path(args.flow).parent / "inputs.json"
    with open(args.inputs, "r") as fin:
        data = json.load(fin)
        if isinstance(data, list):
            data = data[0]
        req["inputs"] = data

    headers = {'Content-Type': 'application/json'}
    if args.api_key:
        headers['Authorization'] = 'Bearer ' + args.api_key
    if args.deployment:
        headers["azureml-model-deployment"] = args.deployment

    resp = requests.post(flow_url, json=req, headers=headers)
    if resp.status_code != 200:
        print(resp.text)
        raise RuntimeError(f"Failed to submit flow to {flow_url}.")
    data = resp.json()
    output_file = Path(args.flow).parent / "output.json"
    with open(output_file, "w") as fout:
        json.dump(data, fout, indent=2)
    print(f"Output is dumped to '{output_file}'.")
    print(f"{len(data['flow_runs'])} flow runs and {len(data['node_runs'])} node runs are returned.")
    for run in data['flow_runs']:
        assert run['status'] == 'Completed', f"Flow run {run['run_id']} not succeeded, got status {run['status']}."
    for run in data["node_runs"]:
        assert run['status'] == 'Completed', f"Node run {run['run_id']} not succeeded, got status {run['status']}."
