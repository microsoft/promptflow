import argparse
import json
import os
from pathlib import Path

import requests
from azureml.core.authentication import InteractiveLoginAuthentication


def create_flow(flow_dir):
    # Construct flow graph
    flow_graph, flow_type, node_variants = construct_flow_graph(Path(flow_dir))

    # Call MT to create flow
    print(f"Starting to create/update flow. Flow dir: {Path(flow_dir).name}. Please wait....")
    create_flow_payload = construct_create_flow_payload(flow_graph, node_variants)
    resp = requests.post(url, json=create_flow_payload, headers=headers)
    if resp.status_code != 200:
        print(f"Error: {resp.status_code} {resp.text}")
        raise Exception(f"Http response got {resp.status_code}")
    create_flow_result = resp.json()
    if create_flow_result["flowId"] is None:
        raise Exception(f"Flow id is None when creating/updating mode {flow_dir}. Please make sure the flow is valid")

    return create_flow_result


def construct_create_flow_payload(flow_graph, node_variants=None):
    if node_variants is not None:
        return {"flowName": flow_graph["name"], "flow": {"flowGraph": flow_graph, "nodeVariants": node_variants}}
    return {"flowName": flow_graph["name"], "flow": {"flowGraph": flow_graph}}


def construct_flow_graph(flow_dir: Path):
    """Construct the flow graph from the flow."""
    with open(flow_dir / "flow.json", "r") as flow_file:
        flow_graph = json.load(flow_file)

    with open(flow_dir / "meta.json", "r") as meta_file:
        meta = json.load(meta_file)

    tools_definition = flow_graph["tools"]
    node_variants = None
    if "node_variants" in meta:
        node_variants_settings_mapping = meta["node_variants"]
        for node, variants_settings_file_name in node_variants_settings_mapping.items():
            with open(flow_dir / variants_settings_file_name, "r") as f:
                variants_settings = json.load(f)
                if node_variants is None:
                    node_variants = {}
                node_variants[node] = variants_settings
    codes = meta["codes"]

    # replace source with codes
    for tool in tools_definition:
        if tool["name"] not in codes:
            continue
        if tool["type"] == "llm":
            tool["code"] = (flow_dir / tool["source"]).read_text()
        elif tool["type"] == "python":
            tool["code"] = (flow_dir / tool["source"]).read_text()
        elif tool["type"] == "prompt":
            tool["code"] = (flow_dir / tool["source"]).read_text()
        else:
            raise ValueError(f"Unsupported tool type: {tool['type']}")
        tool.pop("source")

    # replace name with meta's name
    flow_graph["name"] = meta["name"]
    flow_type = meta["type"]

    return flow_graph, flow_type, node_variants


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--subscription_id", type=str, default="96aede12-2f73-41cb-b983-6d11a904839b")
    parser.add_argument("--resource_group", type=str, default="promptflow")
    parser.add_argument("--workspace_name", type=str, default="promptflow-gallery")
    parser.add_argument("--region", type=str, default="eastus2euap")
    parser.add_argument("--flow_dir", type=str)
    args = parser.parse_args()

    interactive_auth = InteractiveLoginAuthentication()
    headers = interactive_auth.get_authentication_header()
    print("Login successful.")

    if args.region == "master":
        host = "http://master.api.azureml-test.ms/flow/api"
    else:
        host = f"https://master.ml.azure.com/api/{args.region}/flow/api"

    url = (
        f"{host}/subscriptions/{args.subscription_id}/resourcegroups/{args.resource_group}"
        f"/providers/Microsoft.MachineLearningServices/workspaces/{args.workspace_name}/flows"
    )

    print(f"\nChecking flow dir: {args.flow_dir}")
    # check if the flow.json exits
    if not os.path.exists(Path(args.flow_dir) / "flow.json"):
        raise Exception(f"flow.json not found in {args.flow_dir}.")

    create_flow_result = create_flow(args.flow_dir)
    experiment_id = create_flow_result["experimentId"]
    flow_id = create_flow_result["flowId"]
    flow_run_link_format = (
        "https://eastus2euap.ml.azure.com/prompts/flow/{experiment_id}/{flow_id}/details?"
        "wsid=/subscriptions/{subscription}/resourceGroups/{resource_group}/"
        "providers/Microsoft.MachineLearningServices/workspaces/{workspace}&flight=promptflow"
    )
    flow_link = flow_run_link_format.format(
        subscription=args.subscription_id,
        resource_group=args.resource_group,
        workspace=args.workspace_name,
        experiment_id=experiment_id,
        flow_id=flow_id,
    )
    print(f"Flow link to Azure Machine Learning Portal: {flow_link}")
