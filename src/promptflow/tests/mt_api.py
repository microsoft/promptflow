import argparse
import json
from datetime import datetime
from pathlib import Path

import requests
from azureml.core.authentication import InteractiveLoginAuthentication


def construct_create_api_payload(raw_request, flow_type):
    if flow_type is not None:
        return {"flowName": raw_request["name"], "flow": {"flowGraph": raw_request}, "flowType": flow_type}
    else:
        return {"flowName": raw_request["name"], "flow": {"flowGraph": raw_request}}


def construct_submit_api_payload(raw_request, flow_id, batch_inputs=None):
    if batch_inputs is None:
        batch_inputs = []
        for input_name in raw_request["inputs"]:
            batch_inputs.append({input_name: raw_request["inputs"][input_name]["default"]})
    return {
        "flowId": flow_id,
        "flow": {"flowGraph": raw_request, "flowGraphLayout": None},
        "flowRunId": f"run_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "flowSubmitRunSettings": {"runMode": "Flow", "batch_inputs": batch_inputs},
    }


# filter out private params as a workaround for now.
def filter_tool_params(raw_request):
    for tool in raw_request["tools"]:
        if tool["name"] == "Bing.search":
            tool["inputs"] = {p: tool["inputs"][p] for p in tool["inputs"] if p in {"query", "count", "offset"}}
        elif tool["name"] == "AzureContentSafety.analyze_text":
            tool["inputs"] = {p: tool["inputs"][p] for p in tool["inputs"] if p in {"connection", "text"}}


if __name__ == "__main__":
    print(f"{datetime.now()} This script is used to test MT API. It requires you to login to Azure first.")
    interactive_auth = InteractiveLoginAuthentication()
    headers = interactive_auth.get_authentication_header()
    print(f"{datetime.now()} Login successful.")
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=str, required=True)
    parser.add_argument("--api_name", type=str, default="create_or_update", choices=["create_or_update", "submit"])
    parser.add_argument("--region", type=str, default="eastus2euap", choices=["eastus2euap", "master"])
    parser.add_argument("--subscription_id", type=str, default="96aede12-2f73-41cb-b983-6d11a904839b")
    parser.add_argument("--resource_group", type=str, default="promptflow")
    parser.add_argument("--workspace_name", type=str, default="promptflow-canary")
    parser.add_argument("--flow_id", type=str)
    parser.add_argument("--batch_inputs", type=str, default=None)
    parser.add_argument("--flow_type", type=str, default=None)
    args = parser.parse_args()
    if args.api_name == "submit" and args.flow_id is None:
        raise Exception("--flow_id is required when --api_name is 'submit'")

    output_dir = Path(__file__).parent / "api_outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    input_file = Path(args.request)
    api_name = args.api_name
    output_file = output_dir / f"{api_name}_{input_file.name}"
    with open(input_file, "r") as f:
        raw_request = json.load(f)
    print(f"{datetime.now()} Loaded request from {input_file}, api_name={api_name}, output_file={output_file}")
    filter_tool_params(raw_request)

    if args.region == "master":
        host = "http://master.api.azureml-test.ms/flow/api"
    elif args.region == "eastus2euap":
        host = "https://master.ml.azure.com/api/eastus2euap/flow/api"

    if api_name == "create_or_update":
        request = construct_create_api_payload(raw_request, args.flow_type)
        url = (
            f"{host}/subscriptions/{args.subscription_id}/resourcegroups/{args.resource_group}"
            f"/providers/Microsoft.MachineLearningServices/workspaces/{args.workspace_name}/flows"
        )
    elif api_name == "submit":
        if args.batch_inputs is not None:
            with open(args.batch_inputs, "r") as f:
                args.batch_inputs = json.load(f)

        request = construct_submit_api_payload(raw_request, flow_id=args.flow_id, batch_inputs=args.batch_inputs)
        url = (
            f"{host}/subscriptions/{args.subscription_id}/resourcegroups/{args.resource_group}"
            f"/providers/Microsoft.MachineLearningServices/workspaces/{args.workspace_name}/flows/"
            "submit?experimentId=5fbfda62-4e3d-43da-b908-8b8feca82b17"
        )
    else:
        raise Exception(f"Unknown api name {api_name}")

    start = datetime.now()
    print(f"{start} Sending request to {url}")
    resp = requests.post(url, json=request, headers=headers)
    end = datetime.now()
    if resp.status_code != 200:
        print(f"Error: {resp.status_code} {resp.text}")
        raise Exception(f"Http response got {resp.status_code}")
    result = resp.json()
    with open(output_file, "w") as fout:
        json.dump(result, fout, indent=2)
    print(f"{datetime.now()} Http response got 200 in {end - start}, saved to {output_file}")
    if api_name == "create_or_update":
        print(f"Flow id: {result['flowId']}, use it if you want to submit flow run.")
