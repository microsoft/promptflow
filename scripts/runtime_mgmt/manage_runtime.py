# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse

from azure.ai.ml import MLClient, load_compute, load_environment
from azure.identity import AzureCliCredential

from constants import (
    COMPUTE_INSTANCE_YAML,
    ENVIRONMENT_YAML,
)
from pfs_runtime_helper import PFSRuntimeHelper


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subscription-id", type=str)
    parser.add_argument("--resource-group-name", type=str)
    parser.add_argument("--workspace-name", type=str)
    parser.add_argument("--compute-instance-name", type=str)
    parser.add_argument("--runtime-name", type=str)
    return parser.parse_args()


def init_ml_client(
    subscription_id: str,
    resource_group_name: str,
    workspace_name: str,
) -> MLClient:
    return MLClient(
        credential=AzureCliCredential(),
        subscription_id=subscription_id,
        resource_group_name=resource_group_name,
        workspace_name=workspace_name,
    )


def create_compute_instance(ml_client: MLClient) -> str:
    compute_instance = load_compute(source=COMPUTE_INSTANCE_YAML)
    ml_client.compute.begin_create_or_update(compute_instance).wait()
    return compute_instance.name


def delete_compute_instance(ml_client: MLClient, name: str) -> None:
    ml_client.compute.begin_delete(name=name).wait()


def create_environment(ml_client: MLClient) -> str:
    environment = load_environment(source=ENVIRONMENT_YAML)
    env = ml_client.environments.create_or_update(environment)
    # get workspace id from REST workspace object
    resource_group_name = ml_client._operation_scope.resource_group_name
    workspace_name = ml_client._operation_scope.workspace_name
    location = ml_client.workspaces.get(name=workspace_name).location
    workspace_id = ml_client._workspaces._operation.get(
        resource_group_name=resource_group_name, workspace_name=workspace_name
    ).workspace_id
    # concat environment asset id
    asset_id = (
        f"azureml://locations/{location}/workspaces/{workspace_id}"
        f"/environments/{env.name}/versions/{env.version}"
    )
    return asset_id


def main(args: argparse.Namespace):
    ml_client = init_ml_client(
        subscription_id=args.subscription_id,
        resource_group_name=args.resource_group_name,
        workspace_name=args.workspace_name,
    )
    pfs_runtime_helper = PFSRuntimeHelper(ml_client=ml_client)

    # print("deleting runtime...")
    # pfs_runtime_helper.delete_runtime(name=RUNTIME_NAME)
    # print("runtime deleted!")

    # below operations are very heavy:
    # 1. compute instance creation can be very time consuming
    # 2. we might run into quota issue

    # print("deleting compute instance...")
    # delete_compute_instance(ml_client=ml_client)
    # print("compute instance deleted!")

    # print("creating compute instance...")
    # ci_name = create_compute_instance(ml_client=ml_client)
    # print("compute instance created, name:", ci_name)

    print("creating environment...")
    env_asset_id = create_environment(ml_client=ml_client)
    print("created environment, asset id:", env_asset_id)

    print("creating runtime...")
    pfs_runtime_helper.create_runtime(
        name=args.runtime_name,
        env_asset_id=env_asset_id,
        ci_name=args.compute_instance_name,
    )
    print("runtime created!")


if __name__ == "__main__":
    main(args=parse_args())
