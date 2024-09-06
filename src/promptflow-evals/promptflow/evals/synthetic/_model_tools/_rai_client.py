# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os
from typing import Any, Dict
from urllib.parse import urljoin, urlparse

from azure.core.pipeline.policies import AsyncRetryPolicy, RetryMode

from promptflow.evals._http_utils import AsyncHttpPipeline, get_async_http_client, get_http_client
from promptflow.evals._user_agent import USER_AGENT

from ._identity_manager import APITokenManager

api_url = None
if "RAI_SVC_URL" in os.environ:
    api_url = os.environ["RAI_SVC_URL"]
    api_url = api_url.rstrip("/")
    print(f"Found RAI_SVC_URL in environment variable, using {api_url} for the service endpoint.")


class RAIClient:
    """Client for the Responsible AI Service

    :param azure_ai_project: The Azure AI project
    :type azure_ai_project: Dict
    :param token_manager: The token manager
    :type token_manage: ~promptflow.evals.synthetic._model_tools._identity_manager.APITokenManager
    """

    def __init__(self, azure_ai_project: Dict, token_manager: APITokenManager) -> None:
        self.azure_ai_project = azure_ai_project
        self.token_manager = token_manager

        self.contentharm_parameters = None
        self.jailbreaks_dataset = None

        if api_url is not None:
            host = api_url

        else:
            host = self._get_service_discovery_url()
        segments = [
            host.rstrip("/"),
            "raisvc/v1.0/subscriptions",
            self.azure_ai_project["subscription_id"],
            "resourceGroups",
            self.azure_ai_project["resource_group_name"],
            "providers/Microsoft.MachineLearningServices/workspaces",
            self.azure_ai_project["project_name"],
        ]
        self.api_url = "/".join(segments)
        # add a "/" at the end of the url
        self.api_url = self.api_url.rstrip("/") + "/"
        self.parameter_json_endpoint = urljoin(self.api_url, "simulation/template/parameters")
        self.jailbreaks_json_endpoint = urljoin(self.api_url, "simulation/jailbreak")
        self.simulation_submit_endpoint = urljoin(self.api_url, "simulation/chat/completions/submit")
        self.xpia_jailbreaks_json_endpoint = urljoin(self.api_url, "simulation/jailbreak/xpia")

    def _get_service_discovery_url(self):
        bearer_token = self.token_manager.get_token()
        headers = {"Authorization": f"Bearer {bearer_token}", "Content-Type": "application/json"}
        http_client = get_http_client()
        response = http_client.get(  # pylint: disable=too-many-function-args,unexpected-keyword-arg
            f"https://management.azure.com/subscriptions/{self.azure_ai_project['subscription_id']}/"
            f"resourceGroups/{self.azure_ai_project['resource_group_name']}/"
            f"providers/Microsoft.MachineLearningServices/workspaces/{self.azure_ai_project['project_name']}?"
            f"api-version=2023-08-01-preview",
            headers=headers,
            timeout=5,
        )
        if response.status_code != 200:
            raise Exception("Failed to retrieve the discovery service URL")  # pylint: disable=broad-exception-raised
        base_url = urlparse(response.json()["properties"]["discoveryUrl"])
        return f"{base_url.scheme}://{base_url.netloc}"

    def _create_async_client(self) -> AsyncHttpPipeline:
        """Create an async http client with retry mechanism

        Number of retries is set to 6, and the timeout is set to 5 seconds.

        :return: The async http client
        :rtype: ~promptflow.evals._http_utils.AsyncHttpPipeline
        """
        return get_async_http_client().with_policies(
            retry_policy=AsyncRetryPolicy(retry_total=6, retry_backoff_factor=5, retry_mode=RetryMode.Fixed)
        )

    async def get_contentharm_parameters(self) -> Any:
        """Get the content harm parameters, if they exist"""
        if self.contentharm_parameters is None:
            self.contentharm_parameters = await self.get(self.parameter_json_endpoint)

        return self.contentharm_parameters

    async def get_jailbreaks_dataset(self, type: str) -> Any:
        "Get the jailbreaks dataset, if exists"
        if self.jailbreaks_dataset is None:
            if type == "xpia":
                self.jailbreaks_dataset = await self.get(self.xpia_jailbreaks_json_endpoint)
            elif type == "upia":
                self.jailbreaks_dataset = await self.get(self.jailbreaks_json_endpoint)
            else:
                raise ValueError("Invalid type, please provide either 'xpia' or 'upia'")

        return self.jailbreaks_dataset

    async def get(self, url: str) -> Any:
        """Make a GET request to the given url

        :param url: The url
        :type url: str
        :raises ValueError: If the Azure safety evaluation service is not available in the current region
        :return: The response
        :rtype: Any
        """
        token = self.token_manager.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        }

        session = self._create_async_client()
        response = await session.get(url=url, headers=headers)  # pylint: disable=unexpected-keyword-arg

        if response.status_code == 200:
            return response.json()

        raise ValueError(
            "Azure safety evaluation service is not available in your current region, "
            "please go to https://aka.ms/azureaistudiosafetyeval to see which regions are supported"
        )
