import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml
from azure.ai.ml import MLClient
from azure.core.exceptions import ResourceExistsError
from azure.identity import AzureCliCredential

GET_HTTP_METHOD = "GET"
DELETE_HTTP_METHOD = "DELETE"


class RuntimeManager:
    def __init__(self, deployment, merged_pr_number, expiration_time, max_deployment_num):
        self.merged_pr_number = merged_pr_number
        self.expiration_time = expiration_time
        self.max_deployment_num = max_deployment_num
        self.endpoint_name = deployment["endpoint_name"]
        self.ml_client = MLClient(
            credential=AzureCliCredential(),
            subscription_id=deployment["subscription_id"],
            resource_group_name=deployment["resource_group"],
            workspace_name=deployment["workspace_name"],
        )

    def delete_expired_runtimes_and_deployments(self):
        runtimes_list = self.call_mt_api(GET_HTTP_METHOD)
        runtime_name_list = []
        # Delete the exprired runtimes
        print(f"The expiration time: {self.expiration_time} hours")
        for runtime in runtimes_list:
            runtime_name = runtime["runtimeName"]
            # Delete the runtime created by the PR merged into the main branch
            if self.merged_pr_number and runtime_name.startswith(f"pr-{self.merged_pr_number}-"):
                print(
                    f"Delete the runtime {runtime_name!r} created by the PR merged into the main branch:\n"
                    f"{json.dumps(runtime, indent=4)}"
                )
                self.call_mt_api(DELETE_HTTP_METHOD, relative_path=f"{runtime_name}")
                continue
            # Delete the runtime created more than self.expiration_time hours
            if runtime_name.startswith("pr-") or runtime_name.startswith("bu-"):
                runtime_name_list.append(runtime_name)
                if self.is_expired(runtime["modifiedOn"]):
                    print(
                        f"Delete the runtime {runtime_name!r} created more than {self.expiration_time}h:\n"
                        f"{json.dumps(runtime, indent=4)}"
                    )
                    self.call_mt_api(DELETE_HTTP_METHOD, relative_path=f"{runtime_name}")

        # Delete the deployments that are not in the runtimes list
        #
        # Because there are at most 20 deployments under an endpoint, the following logic will
        # only be run when the number of deployments more than self.max_deployment_num.
        endpoint = self.ml_client.online_endpoints.get(self.endpoint_name)
        print(f"The max deployments number: {self.max_deployment_num}")
        if len(endpoint.traffic) > self.max_deployment_num:
            deployment_list = [
                deployment
                for deployment in endpoint.traffic
                if deployment.startswith("pr-") or deployment.startswith("bu-")
            ]
            self.delete_extra_deployment(deployment_list, runtime_name_list)

    def delete_extra_deployment(self, deployment_list, runtime_list):
        deployment_set = set(map(str.lower, deployment_list))
        runtime_set = set(map(str.lower, runtime_list))
        extra_deployments = deployment_set.difference(runtime_set)
        for deployment in extra_deployments:
            print(f"Deleting deployment: {deployment}")
            try:
                self.ml_client.online_deployments.begin_delete(name=deployment, endpoint_name=self.endpoint_name)
            except ResourceExistsError as e:
                print(f"Failed to delete deployment: {deployment}, error: {e}")
                pass

    def call_mt_api(self, method, relative_path=""):
        token = self.ml_client._credential.get_token("https://management.azure.com/.default")
        headers = {"Authorization": f"Bearer {token.token}"}

        workspace = self.ml_client.workspaces.get()
        discovery_url = requests.get(workspace.discovery_url, headers=headers)
        api_host = discovery_url.json().get("api")
        base_url = f"{api_host}/flow/api{workspace.id}"
        url = f"{base_url}/flowRuntimes/{relative_path}?asyncCall=true"

        if method == GET_HTTP_METHOD:
            return requests.get(url, headers=headers).json()
        elif method == DELETE_HTTP_METHOD:
            return requests.delete(url, headers=headers)
        return None

    def is_expired(self, update_time_str):
        current_time = datetime.now().astimezone(timezone.utc)
        update_time = datetime.strptime(update_time_str[:-7], "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=timezone.utc)
        hour_difference = (current_time - update_time).total_seconds() / 3600
        print(f"current_time: {current_time}, update_time: {update_time}, hour_difference: {hour_difference}")
        return hour_difference >= self.expiration_time


if __name__ == "__main__":
    # Parse the arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-file", type=str, required=True, help="Path to model file containing workspace info")
    parser.add_argument("--build-message", type=str, help="The build message", default="")
    parser.add_argument(
        "--expiration-time",
        type=int,
        help="The runtimes will be deleted if it is created exceeds expiration time",
        default=8,
    )
    parser.add_argument(
        "--max-deployment-num",
        type=int,
        help="When deployments number exceeds this value, deployments without corresponding runtimes will be deleted",
        default=18,
    )
    args = parser.parse_args()

    # Get the deployment config from the model file
    model_file = Path(args.model_file).resolve().absolute()
    if not model_file.exists():
        raise FileNotFoundError(f"Missing {model_file!r}, please update the file path if it is moved elsewhere.")
    with open(model_file, "r") as f:
        model_config = yaml.safe_load(f)
    deployment = model_config["deployment"]
    print(f"deployment_config: {json.dumps(deployment, indent=4)}")

    # Get the PR number of the latest merged main branch
    merged_pr_number = None
    if args.build_message:
        match = re.search(r"Merged PR (\d+):", args.build_message)
        if match:
            merged_pr_number = match.group(1)
            print(f"The PR Number of the latest merged main branch: {merged_pr_number}")

    # Init runtime manager and delete the expired runtimes and deployments
    runtime_manager = RuntimeManager(deployment, merged_pr_number, args.expiration_time, args.max_deployment_num)
    runtime_manager.delete_expired_runtimes_and_deployments()
