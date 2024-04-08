# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging
import os
from typing import Any

from promptflow.evals.synthetic.simulator._model_tools.models import AsyncHTTPClientWithRetry

api_url = None
if "rai_svc_url" in os.environ:
    api_url = os.environ["rai_svc_url"]
    api_url = api_url.rstrip("/")
    print(f"Found rai_svc_url in environment variable, using {api_url} for rai service endpoint.")


class RAIClient:  # pylint: disable=client-accepts-api-version-keyword
    # pylint: disable=missing-client-constructor-parameter-credential, missing-client-constructor-parameter-kwargs
    def __init__(self, ml_client: Any, token_manager: Any) -> None:
        self.ml_client = ml_client
        self.token_manager = token_manager

        self.contentharm_parameters = None
        self.jailbreaks_dataset = None

        if api_url is not None:
            host = api_url
        else:
            host = self.ml_client.jobs._api_url

        self.api_url = (
            f"{host}/"
            + f"raisvc/v1.0/subscriptions/{self.ml_client.subscription_id}/"
            + f"resourceGroups/{self.ml_client.resource_group_name}/"
            + f"providers/Microsoft.MachineLearningServices/workspaces/{self.ml_client.workspace_name}/"
        )

        self.parameter_json_endpoint = self.api_url + "simulation/template/parameters"
        self.jailbreaks_json_endpoint = self.api_url + "simulation/jailbreak"
        self.simulation_submit_endpoint = self.api_url + "simulation/chat/completions/submit"

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
        token = await self.token_manager.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        async with self._create_async_client().client as session:
            async with session.get(url=url, headers=headers) as response:
                if response.status == 200:
                    response = await response.json()
                    return response

        raise ValueError("Unable to retrieve requested resource from rai service.")
