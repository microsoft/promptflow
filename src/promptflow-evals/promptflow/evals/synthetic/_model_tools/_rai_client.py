# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging
import os
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

from promptflow.evals._user_agent import USER_AGENT

from ._async_http_client import AsyncHTTPClientWithRetry

api_url = None
if "RAI_SVC_URL" in os.environ:
    api_url = os.environ["RAI_SVC_URL"]
    api_url = api_url.rstrip("/")
    print(f"Found RAI_SVC_URL in environment variable, using {api_url} for the service endpoint.")


class RAIClient:
    def __init__(self, azure_ai_project: dict, token_manager: Any) -> None:
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

    def _get_service_discovery_url(self):
        bearer_token = self.token_manager.get_token()
        headers = {"Authorization": f"Bearer {bearer_token}", "Content-Type": "application/json"}
        response = requests.get(
            f"https://management.azure.com/subscriptions/{self.azure_ai_project['subscription_id']}/"
            f"resourceGroups/{self.azure_ai_project['resource_group_name']}/"
            f"providers/Microsoft.MachineLearningServices/workspaces/{self.azure_ai_project['project_name']}?"
            f"api-version=2023-08-01-preview",
            headers=headers,
            timeout=5,
        )
        if response.status_code != 200:
            raise Exception("Failed to retrieve the discovery service URL")
        base_url = urlparse(response.json()["properties"]["discoveryUrl"])
        return f"{base_url.scheme}://{base_url.netloc}"

    def _create_async_client(self):
        return AsyncHTTPClientWithRetry(n_retry=6, retry_timeout=5, logger=logging.getLogger())

    async def get_contentharm_parameters(self) -> Any:
        if self.contentharm_parameters is None:
            self.contentharm_parameters = await self.get(self.parameter_json_endpoint)

        return self.contentharm_parameters

    async def get_jailbreaks_dataset(self) -> Any:
        if self.jailbreaks_dataset is None:
            self.jailbreaks_dataset = await self.get(self.jailbreaks_json_endpoint)

        return self.jailbreaks_dataset

    async def get(self, url: str) -> Any:
        token = self.token_manager.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        }

        async with self._create_async_client().client as session:
            async with session.get(url=url, headers=headers) as response:
                if response.status == 200:
                    response = await response.json()
                    return response

        raise ValueError(
            "Azure safety evaluation service is not available in your current region, "
            "please go to https://aka.ms/azureaistudiosafetyeval to see which regions are supported"
        )
