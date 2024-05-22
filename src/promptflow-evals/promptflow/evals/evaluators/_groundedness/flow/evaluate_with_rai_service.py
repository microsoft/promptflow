import importlib.metadata
import json
import time
from typing import List
from urllib.parse import urlparse

import requests
from azure.core.credentials import TokenCredential
from azure.identity import DefaultAzureCredential
from constants import EvaluationMetrics, RAIService, Tasks

from promptflow.core import tool

try:
    version = importlib.metadata.version("promptflow-evals")
except importlib.metadata.PackageNotFoundError:
    version = "unknown"
USER_AGENT = "{}/{}".format("promptflow-evals", version)


def ensure_service_availability(rai_svc_url: str):
    svc_liveness_url = rai_svc_url.split("/subscriptions")[0] + "/meta/version"
    response = requests.get(svc_liveness_url)
    if response.status_code != 200:
        raise Exception("RAI service is not available in this region")


def submit_request(question: str, answer: str, context: str, rai_svc_url: str, credential: TokenCredential):
    user_text = {
        "question": question,
        "answer": answer,
        "context": context,
    }
    user_text_json = json.dumps(user_text)
    payload = {
        "UserTextList": [user_text_json],
        "AnnotationTask": Tasks.GROUNDEDNESS,
        "MetricList": [EvaluationMetrics.GROUNDEDNESS],
    }

    url = rai_svc_url + "/submitannotation"
    bearer_token = credential.get_token("https://management.azure.com/.default").token
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }

    response = requests.post(url, json=payload, headers=headers)
    if response.status_code != 202:
        print("Fail evaluating '%s' with error message: %s" % (payload["UserTextList"], response.text))
        response.raise_for_status()

    result = response.json()
    operation_id = result["location"].split("/")[-1]
    return operation_id


def fetch_result(operation_id: str, rai_svc_url: str, credential: TokenCredential):
    start = time.time()
    request_count = 0

    url = rai_svc_url + "/operations/" + operation_id
    bearer_token = credential.get_token("https://management.azure.com/.default").token
    headers = {"Authorization": f"Bearer {bearer_token}", "Content-Type": "application/json"}

    while True:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()

        time_elapsed = time.time() - start
        if time_elapsed > RAIService.TIMEOUT:
            raise TimeoutError(f"Fetching annotation result times out after {time_elapsed:.2f} seconds")

        request_count += 1
        sleep_time = RAIService.SLEEP_TIME**request_count
        time.sleep(sleep_time)


def parse_response(batch_response: List[dict]):
    response = batch_response[0]
    if EvaluationMetrics.GROUNDEDNESS in response:
        json_payload = response[EvaluationMetrics.GROUNDEDNESS]
        try:
            result = json.loads(json_payload)
            return result
        except json.JSONDecodeError:
            return None
    return None


def _get_service_discovery_url(azure_ai_project, credential):
    bearer_token = credential.get_token("https://management.azure.com/.default").token
    headers = {"Authorization": f"Bearer {bearer_token}", "Content-Type": "application/json"}
    response = requests.get(
        f"https://management.azure.com/subscriptions/{azure_ai_project['subscription_id']}/"
        f"resourceGroups/{azure_ai_project['resource_group_name']}/"
        f"providers/Microsoft.MachineLearningServices/workspaces/{azure_ai_project['project_name']}?"
        f"api-version=2023-08-01-preview",
        headers=headers,
        timeout=5,
    )
    if response.status_code != 200:
        raise Exception("Failed to retrieve the discovery service URL")
    base_url = urlparse(response.json()["properties"]["discoveryUrl"])
    return f"{base_url.scheme}://{base_url.netloc}"


def get_rai_svc_url(project_scope: dict, credential: TokenCredential):
    discovery_url = _get_service_discovery_url(azure_ai_project=project_scope, credential=credential)
    subscription_id = project_scope["subscription_id"]
    resource_group_name = project_scope["resource_group_name"]
    project_name = project_scope["project_name"]
    base_url = discovery_url.rstrip("/")
    rai_url = (
        f"{base_url}/raisvc/v1.0"
        f"/subscriptions/{subscription_id}"
        f"/resourceGroups/{resource_group_name}"
        f"/providers/Microsoft.MachineLearningServices/workspaces/{project_name}"
    )
    return rai_url


@tool
def evaluate_with_rai_service(
    question: str, answer: str, context: str, project_scope: dict, credential: TokenCredential
):
    # Use DefaultAzureCredential if no credential is provided
    # This is for the for batch run scenario as the credential cannot be serialized by promoptflow
    if credential is None or credential == {}:
        credential = DefaultAzureCredential()

    # Get RAI service URL from discovery service and check service availability
    rai_svc_url = get_rai_svc_url(project_scope, credential)
    ensure_service_availability(rai_svc_url)

    # Submit annotation request and fetch result
    operation_id = submit_request(question, answer, context, rai_svc_url, credential)
    annotation_response = fetch_result(operation_id, rai_svc_url, credential)
    result = parse_response(annotation_response)

    return result
