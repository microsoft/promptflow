import argparse
import json
import os
from datetime import datetime
from pathlib import Path

import requests
from prepare_tests import convert_request_to_raw

# We need to add the following line to make sure the connections can be correctly loaded.
import promptflow.tools  # noqa: F401
from promptflow._constants import PROMPTFLOW_CONNECTIONS
from promptflow.contracts.run_mode import RunMode
from promptflow.core.connection_manager import ConnectionManager


def call_submit_batch(url, input_file, headers, connections, run_mode=RunMode.Flow):
    os.environ[PROMPTFLOW_CONNECTIONS] = connections
    with open(input_file, "r") as f:
        batch_request = json.load(f)
    batch_request["connections"] = ConnectionManager.init_from_env().to_connections_dict()
    if "bulk_test_id" in batch_request:
        run_mode = RunMode.BulkTest
    raw_request = convert_request_to_raw(
        batch_request,
        source_run_id=input_file.stem,
        run_mode=run_mode,
    )
    with open(output_dir / f"{input_file.stem}_raw.json", "w") as fout:
        json.dump(raw_request, fout, indent=2)
    return requests.post(url, json=raw_request, headers=headers)


def call_meta(url, input_file, headers):
    with open(input_file, "r", encoding="utf-8") as fin:
        data = fin.read()
    if input_file.suffix == ".jinja2":
        url = url + "?tool_type=llm&name=intent"
    return requests.post(url, data=data, headers=headers)


def ensure_response(resp, output_file, is_submit=False):
    if resp.status_code != 200:
        print(f"Error: {resp.status_code}")
        try:
            data = resp.json()
            for k, v in data.items():
                print(f"{k}: {v}")
        except json.decoder.JSONDecodeError:
            print(resp.text)
        raise Exception(f"Http response got {resp.status_code}")
    result = resp.json()
    with open(output_file, "w") as fout:
        json.dump(result, fout, indent=2)

    if not is_submit:
        print(resp.text)
        return

    if "error" in result:
        raise Exception(f"Error in result: {result['error']}")
    for run in result["flow_runs"]:
        if run["status"] != "Completed":
            for k, v in run["error"].items():
                print(f"{k}: {v}")
            print(f"See response for more details in '{output_file}'.")
            raise Exception(f"Run {run['run_id']} failed due to {run['error']['message']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=str, required=True)
    parser.add_argument("--url", type=str, default="http://localhost:5000/submit_batch_request")
    parser.add_argument("--api_key", default=None)
    parser.add_argument("--deployment", default="green")
    parser.add_argument("--connections", default="connections.json")
    args = parser.parse_args()
    output_dir = Path(__file__).parent / "api_outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    input_file = Path(args.request)
    output_file = output_dir / input_file.name
    start = datetime.now()
    headers = {}
    if args.api_key:
        headers = {"Authorization": f"Bearer {args.api_key}", "azureml-model-deployment": args.deployment}

    is_submit = not args.url.endswith("meta")
    if not is_submit:
        resp = call_meta(args.url, input_file, headers)
    else:
        resp = call_submit_batch(args.url, input_file, headers, args.connections)
    end = datetime.now()
    ensure_response(resp, output_file, is_submit)

    print(f"{datetime.now()} Http response got 200 in {end - start}, saved to '{output_file}'.")
