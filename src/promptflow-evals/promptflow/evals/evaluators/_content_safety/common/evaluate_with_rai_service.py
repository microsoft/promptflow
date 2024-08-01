# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import asyncio
import importlib.metadata
import re
import time
from ast import literal_eval
from typing import Dict, List
from urllib.parse import urlparse

import httpx
import jwt
import numpy as np
from azure.core.credentials import TokenCredential
from azure.identity import DefaultAzureCredential

try:
    from .constants import CommonConstants, EvaluationMetrics, RAIService, Tasks
    from .utils import get_harm_severity_level
except ImportError:
    from constants import CommonConstants, EvaluationMetrics, RAIService, Tasks
    from utils import get_harm_severity_level

try:
    version = importlib.metadata.version("promptflow-evals")
except importlib.metadata.PackageNotFoundError:
    version = "unknown"
USER_AGENT = "{}/{}".format("promptflow-evals", version)


def get_common_headers(token: str) -> Dict:
    """Get common headers for the HTTP request

    :param token: The Azure authentication token.
    :type token: str
    :return: The common headers.
    :rtype: Dict
    """
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        # Handle "RuntimeError: Event loop is closed" from httpx AsyncClient
        # https://github.com/encode/httpx/discussions/2959
        "Connection": "close",
    }


async def ensure_service_availability(rai_svc_url: str, token: str, capability: str = None) -> None:
    """Check if the Responsible AI service is available in the region and has the required capability, if relevant.

    :param rai_svc_url: The Responsible AI service URL.
    :type rai_svc_url: str
    :param token: The Azure authentication token.
    :type token: str
    :param capability: The capability to check. Default is None.
    :type capability: str
    :raises Exception: If the service is not available in the region or the capability is not available.
    """
    headers = get_common_headers(token)
    svc_liveness_url = rai_svc_url + "/checkannotation"

    async with httpx.AsyncClient() as client:
        response = await client.get(svc_liveness_url, headers=headers, timeout=CommonConstants.DEFAULT_HTTP_TIMEOUT)

    if response.status_code != 200:
        raise Exception(  # pylint: disable=broad-exception-raised
            f"RAI service is not available in this region. Status Code: {response.status_code}"
        )

    capabilities = response.json()

    if capability and capability not in capabilities:
        raise Exception(  # pylint: disable=broad-exception-raised
            f"Capability '{capability}' is not available in this region"
        )


async def submit_request(question: str, answer: str, metric: str, rai_svc_url: str, token: str) -> str:
    """Submit request to Responsible AI service for evaluation and return operation ID

    :param question: The question to evaluate.
    :type question: str
    :param answer: The answer to evaluate.
    :type answer: str
    :param metric: The evaluation metric to use.
    :type metric: str
    :param rai_svc_url: The Responsible AI service URL.
    :type rai_svc_url: str
    :param token: The Azure authentication token.
    :type token: str
    :return: The operation ID.
    :rtype: str
    """
    user_text = f"<Human>{question}</><System>{answer}</>"
    normalized_user_text = user_text.replace("'", '\\"')
    payload = {"UserTextList": [normalized_user_text], "AnnotationTask": Tasks.CONTENT_HARM, "MetricList": [metric]}

    url = rai_svc_url + "/submitannotation"
    headers = get_common_headers(token)

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers, timeout=CommonConstants.DEFAULT_HTTP_TIMEOUT)

    if response.status_code != 202:
        print("Fail evaluating '%s' with error message: %s" % (payload["UserTextList"], response.text))
        response.raise_for_status()

    result = response.json()
    operation_id = result["location"].split("/")[-1]
    return operation_id


async def fetch_result(operation_id: str, rai_svc_url: str, credential: TokenCredential, token: str) -> Dict:
    """Fetch the annotation result from Responsible AI service

    :param operation_id: The operation ID.
    :type operation_id: str
    :param rai_svc_url: The Responsible AI service URL.
    :type rai_svc_url: str
    :param credential: The Azure authentication credential.
    :type credential: ~azure.core.credentials.TokenCredential
    :param token: The Azure authentication token.
    :type token: str
    :return: The annotation result.
    :rtype: Dict
    """
    start = time.time()
    request_count = 0

    url = rai_svc_url + "/operations/" + operation_id
    while True:
        token = await fetch_or_reuse_token(credential, token)
        headers = get_common_headers(token)

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=CommonConstants.DEFAULT_HTTP_TIMEOUT)

        if response.status_code == 200:
            return response.json()

        request_count += 1
        time_elapsed = time.time() - start
        if time_elapsed > RAIService.TIMEOUT:
            raise TimeoutError(f"Fetching annotation result {request_count} times out after {time_elapsed:.2f} seconds")

        sleep_time = RAIService.SLEEP_TIME**request_count
        await asyncio.sleep(sleep_time)


def parse_response(  # pylint: disable=too-many-branches,too-many-statements
    batch_response: List[Dict], metric_name: str
) -> List[List[dict]]:
    """Parse the annotation response from Responsible AI service

    :param batch_response: The annotation response from Responsible AI service.
    :type batch_response: List[Dict]
    :param metric_name: The evaluation metric to use.
    :type metric_name: str
    :return: The parsed annotation result.
    :rtype: List[List[Dict]]
    """
    # Fix the metric name if it's "hate_fairness"
    # Eventually we will remove this fix once the RAI service is updated
    key = metric_name
    if key == EvaluationMetrics.HATE_FAIRNESS:
        key = EvaluationMetrics.HATE_UNFAIRNESS

    result = {key: np.nan, key + "_score": np.nan, key + "_reason": ""}

    response = batch_response[0]
    if metric_name not in response:
        return result

    try:
        harm_response = literal_eval(response[metric_name])
    except Exception:  # pylint: disable=broad-exception-caught
        harm_response = response[metric_name]

    if harm_response != "" and isinstance(harm_response, dict):
        # check if "output" is one key in harm_response
        if "output" in harm_response:
            harm_response = harm_response["output"]

        # get content harm metric_value
        if "label" in harm_response:
            metric_value = harm_response["label"]
        elif "valid" in harm_response:
            metric_value = 0 if harm_response["valid"] else np.nan
        else:
            metric_value = np.nan

        # get reason
        if "reasoning" in harm_response:
            reason = harm_response["reasoning"]
        elif "reason" in harm_response:
            reason = harm_response["reason"]
        else:
            reason = ""
    elif harm_response != "" and isinstance(harm_response, str):
        metric_value_match = re.findall(r"(\b[0-7])\b", harm_response)
        if metric_value_match:
            metric_value = int(metric_value_match[0])
        else:
            metric_value = np.nan
        reason = harm_response
    elif harm_response != "" and isinstance(harm_response, (int, float)):
        if 0 < harm_response <= 7:
            metric_value = harm_response
        else:
            metric_value = np.nan
        reason = ""
    else:
        metric_value = np.nan
        reason = ""

    harm_score = metric_value
    if not np.isnan(metric_value):
        # int(np.nan) causes a value error, and np.nan is already handled
        # by get_harm_severity_level
        harm_score = int(metric_value)
    result[key] = get_harm_severity_level(harm_score)
    result[key + "_score"] = harm_score
    result[key + "_reason"] = reason

    return result


async def _get_service_discovery_url(azure_ai_project: dict, token: str) -> str:
    """Get the discovery service URL for the Azure AI project

    :param azure_ai_project: The Azure AI project details.
    :type azure_ai_project: Dict
    :param token: The Azure authentication token.
    :type token: str
    :return: The discovery service URL.
    :rtype: str
    """
    headers = get_common_headers(token)
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://management.azure.com/subscriptions/{azure_ai_project['subscription_id']}/"
            f"resourceGroups/{azure_ai_project['resource_group_name']}/"
            f"providers/Microsoft.MachineLearningServices/workspaces/{azure_ai_project['project_name']}?"
            f"api-version=2023-08-01-preview",
            headers=headers,
            timeout=CommonConstants.DEFAULT_HTTP_TIMEOUT,
        )
    if response.status_code != 200:
        raise Exception("Failed to retrieve the discovery service URL")  # pylint: disable=broad-exception-raised
    base_url = urlparse(response.json()["properties"]["discoveryUrl"])
    return f"{base_url.scheme}://{base_url.netloc}"


async def get_rai_svc_url(project_scope: dict, token: str) -> str:
    """Get the Responsible AI service URL

    :param project_scope: The Azure AI project scope details.
    :type project_scope: Dict
    :param token: The Azure authentication token.
    :type token: str
    :return: The Responsible AI service URL.
    :rtype: str
    """
    discovery_url = await _get_service_discovery_url(azure_ai_project=project_scope, token=token)
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


async def fetch_or_reuse_token(credential: TokenCredential, token: str = None) -> str:
    """Get token. Fetch a new token if the current token is near expiry

       :param credential: The Azure authentication credential.
       :type credential:
    ~azure.core.credentials.TokenCredential
       :param token: The Azure authentication token. Defaults to None. If none, a new token will be fetched.
       :type token: str
       :return: The Azure authentication token.
    """
    acquire_new_token = True
    try:
        if token:
            # Decode the token to get its expiration time
            decoded_token = jwt.decode(token, options={"verify_signature": False})
            exp_time = decoded_token["exp"]
            current_time = time.time()

            # Check if the token is near expiry
            if (exp_time - current_time) >= 300:
                acquire_new_token = False
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    if acquire_new_token:
        token = credential.get_token("https://management.azure.com/.default").token

    return token


async def evaluate_with_rai_service(
    question: str, answer: str, metric_name: str, project_scope: dict, credential: TokenCredential
):
    """ "Evaluate the content safety of the answer using Responsible AI service

       :param question: The question to evaluate.
       :type question: str
       :param answer: The answer to evaluate.
       :type answer: str
       :param metric_name: The evaluation metric to use.
       :type metric_name: str
       :param project_scope: The Azure AI project scope details.
       :type project_scope: Dict
       :param credential: The Azure authentication credential.
       :type credential:
    ~azure.core.credentials.TokenCredential
       :return: The parsed annotation result.
       :rtype: List[List[Dict]]
    """
    # Use DefaultAzureCredential if no credential is provided
    # This is for the for batch run scenario as the credential cannot be serialized by promoptflow
    if credential is None or credential == {}:
        credential = DefaultAzureCredential()

    # Get RAI service URL from discovery service and check service availability
    token = await fetch_or_reuse_token(credential)
    rai_svc_url = await get_rai_svc_url(project_scope, token)
    await ensure_service_availability(rai_svc_url, token, Tasks.CONTENT_HARM)

    # Submit annotation request and fetch result
    operation_id = await submit_request(question, answer, metric_name, rai_svc_url, token)
    annotation_response = await fetch_result(operation_id, rai_svc_url, credential, token)
    result = parse_response(annotation_response, metric_name)

    return result
