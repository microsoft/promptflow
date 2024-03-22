from promptflow import tool
import time
from constants import RAIService, Tasks
from typing import List
import numpy as np
import re
from utils import get_harm_severity_level
from azure.core.credentials import TokenCredential
from azure.identity import DefaultAzureCredential
import requests

def ensure_service_availability(rai_svc_url: str):
    svc_liveness_url = rai_svc_url.split("/subscriptions")[0] + "/meta/version"
    response = requests.get(svc_liveness_url)
    if response.status_code != 200:
        raise Exception("RAI service is not available in this region")

def submit_request(question: str, answer: str, metric: str, rai_svc_url: str, credential: TokenCredential):
    user_text = f"<Human>{question}</><System>{answer}</>"
    normalized_user_text = user_text.replace("'", "\\\"")
    payload = {
        "UserTextList": [normalized_user_text],
        "AnnotationTask": Tasks.CONTENT_HARM,
        "MetricList": [metric]
    }

    url = rai_svc_url + "/submitannotation"
    bearer_token = credential.get_token("https://management.azure.com/.default").token
    headers = {
        'Authorization': f'Bearer {bearer_token}',
        'Content-Type': 'application/json'
    }

    response = requests.post(url, json=payload, headers=headers)
    if response.status_code != 202:
        print("Fail evaluating '%s' with error message: %s" %(payload["UserTextList"], response.text))
        response.raise_for_status()

    result = response.json()
    operation_id = result["location"].split("/")[-1]
    return operation_id

def fetch_result(operation_id: str, rai_svc_url: str, credential: TokenCredential):
    start = time.time()
    request_count = 0

    url = rai_svc_url + "/operations/" + operation_id
    bearer_token = credential.get_token("https://management.azure.com/.default").token
    headers = {
        'Authorization': f'Bearer {bearer_token}',
        'Content-Type': 'application/json'
    }

    while True:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()

        time_elapsed = time.time() - start
        if time_elapsed > RAIService.TIMEOUT:
            raise TimeoutError(f"Fetching annotation result times out after {time_elapsed:.2f} seconds")

        request_count += 1
        sleep_time = RAIService.SLEEP_TIME ** request_count
        time.sleep(sleep_time)

def parse_response(batch_response: List[dict], metric_name: str) -> List[List[dict]]:
    # Fix the metric name if it's "hate_fairness"
    # Eventually we will remove this fix once the RAI service is updated
    key = metric_name
    if key == "hate_fairness":
        key = "hate_unfairness"

    result = {
        key: np.nan,
        key + "_score": np.nan,
        key + "_reason": ""
    }

    response = batch_response[0]
    if metric_name not in response:
        return result

    try:
        harm_response = eval(response[metric_name])
    except NameError as e:
        # fix the eval error if there's "true" in the response
        m = re.findall(r"name '(\w+)' is not defined", str(e))
        if m:
            for word in m:
                response[metric_name] = response[metric_name].replace(word, word.title())
            harm_response = eval(response[metric_name])
        else:
            harm_response = ""
    except:
        harm_response = response[metric_name]

    if harm_response != "" and isinstance(harm_response, dict):
        ### check if "output" is one key in harm_response
        if "output" in harm_response:
            harm_response = harm_response["output"]

        # get content harm metric_value
        if 'label' in harm_response:
            metric_value = harm_response['label']
        elif 'valid' in harm_response:
            metric_value = 0 if harm_response['valid'] else np.nan
        else:
            metric_value = np.nan

        # get reason
        if "reasoning" in harm_response:
            reason = harm_response['reasoning']
        elif "reason" in harm_response:
            reason = harm_response['reason']
        else:
            reason = ""
    elif harm_response != "" and isinstance(harm_response, str):
        metric_value_match = re.findall(r"(\b[0-7])\b", harm_response)
        if metric_value_match:
            metric_value = int(metric_value_match[0])
        else:
            metric_value = np.nan
        reason = harm_response
    elif harm_response != "" and (isinstance(harm_response, int) or isinstance(harm_response, float)):
        if harm_response >= 0 and harm_response <= 7:
            metric_value = harm_response
        else:
            metric_value = np.nan
        reason = ""
    else:
        metric_value = np.nan
        reason = ""

    harm_score = int(metric_value)
    result[key] = get_harm_severity_level(harm_score)
    result[key + "_score"] = harm_score
    result[key + "_reason"] = reason

    return result

def get_rai_svc_url(project_scope: dict, credential: TokenCredential):
    from azure.ai.ml import MLClient
    ml_client = MLClient(
        credential=credential,
        subscription_id=project_scope['subscription_id'],
        resource_group_name=project_scope['resource_group_name'])

    ws = ml_client.workspaces.get(project_scope['project_name'])
    response = requests.get(ws.discovery_url)
    if response.status_code != 200:
        raise Exception("Failed to retrieve the discovery service URL")

    subscription_id = project_scope['subscription_id']
    resource_group_name = project_scope['resource_group_name']
    project_name = project_scope['project_name']
    base_url = response.json()["api"]
    rai_url = f"{base_url}/raisvc/v1.0" \
              f"/subscriptions/{subscription_id}" \
              f"/resourceGroups/{resource_group_name}" \
              f"/providers/Microsoft.MachineLearningServices/workspaces/{project_name}"

    return rai_url

@tool
def evaluate_with_rai_service(
    question: str,
    answer: str,
    metric_name: str,
    project_scope: dict,
    credential: TokenCredential):

    # Use DefaultAzureCredential if no credential is provided
    # This is for the for batch run scenario as the credential cannot be serialized by promoptflow
    if credential is None or credential == {}:
        credential = DefaultAzureCredential()

    # Get RAI service URL from discovery service and check service availability
    rai_svc_url = get_rai_svc_url(project_scope, credential)
    ensure_service_availability(rai_svc_url)

    # Submit annotation request and fetch result
    operation_id = submit_request(question, answer, metric_name, rai_svc_url, credential)
    annotation_response = fetch_result(operation_id, rai_svc_url, credential)
    result = parse_response(annotation_response, metric_name)

    return result
