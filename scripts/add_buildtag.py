import argparse
import json
from pathlib import Path

import yaml
from azure.ai.ml import MLClient
from azure.identity import AzureCliCredential

if __name__ == "__main__":
    # Parse the arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-file", type=str, required=True, help="Path to model file containing workspace info")
    args = parser.parse_args()

    # Get the deployment config from the model file
    model_file = Path(args.model_file).resolve().absolute()
    if not model_file.exists():
        raise FileNotFoundError(f"Missing {model_file!r}, please update the file path if it is moved elsewhere.")
    with open(model_file, "r") as f:
        model_config = yaml.safe_load(f)
    deployment = model_config["deployment"]
    print(f"deployment_config: {json.dumps(deployment, indent=4)}")

    ml_client = MLClient(
        credential=AzureCliCredential(),
        subscription_id=deployment["subscription_id"],
        resource_group_name=deployment["resource_group"],
        workspace_name=deployment["workspace_name"],
    )

    workspace = ml_client.workspaces.get()
    endpoint_name = deployment["endpoint_name"]
    runtime_name = deployment["runtime_name"]

    print(f"##vso[build.addbuildtag]region-{workspace.location}")
    print(f"##vso[build.addbuildtag]workspace-{workspace.name}")
    print(f"##vso[build.addbuildtag]endpoint-{endpoint_name}")
    print(f"##vso[build.addbuildtag]runtime-{runtime_name}")
