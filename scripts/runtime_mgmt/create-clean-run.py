# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse

from azure.ai.ml import MLClient
from azure.identity import AzureCliCredential
from promptflow.azure import PFClient

TEST_RUNTIME = "test-runtime-ci"
EXAMPLE_RUNTIME = "example-runtime-ci"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", help="Path to config.json", type=str)
    return parser.parse_args()


def init_client(config_json_path: str) -> PFClient:
    subscription_id, resource_group_name, workspace_name = MLClient._get_workspace_info(config_json_path)
    return PFClient(
        credential=AzureCliCredential(),
        subscription_id=subscription_id,
        resource_group_name=resource_group_name,
        workspace_name=workspace_name,
    )


def main(args: argparse.Namespace):
    client = init_client(config_json_path=args.path)
    for runtime in (TEST_RUNTIME, EXAMPLE_RUNTIME):
        run = client.run(
            flow="./clean-disk-flow",
            data="./clean-disk-flow/data.jsonl",
            runtime=runtime,
        )
        client.runs.stream(run=run.name)


if __name__ == "__main__":
    main(args=parse_args())
