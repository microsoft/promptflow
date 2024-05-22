# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import asyncio
import copy
import json
import logging
import time
import uuid
from typing import List

from aiohttp.web import HTTPException
from aiohttp_retry import JitterRetry, RetryClient

from promptflow.evals._user_agent import USER_AGENT

from .models import AsyncHTTPClientWithRetry, OpenAIChatCompletionsModel


class SimulationRequestDTO:
    def __init__(self, url, headers, payload, params, templatekey, template_parameters):
        self.url = url
        self.headers = headers
        self.json = json.dumps(payload)
        self.params = params
        self.templatekey = templatekey
        self.templateParameters = template_parameters

    def to_dict(self):
        if self.templateParameters is not None:
            self.templateParameters = {str(k): str(v) for k, v in self.templateParameters.items()}
        return self.__dict__

    def to_json(self):
        return json.dumps(self.__dict__)


class ProxyChatCompletionsModel(OpenAIChatCompletionsModel):
    def __init__(self, name, template_key, template_parameters, *args, **kwargs):
        self.tkey = template_key
        self.tparam = template_parameters
        self.result_url = None

        super().__init__(name=name, *args, **kwargs)

    def format_request_data(self, messages: List[dict], **request_params):  # type: ignore[override]
        request_data = {"messages": messages, **self.get_model_params()}
        request_data.update(request_params)
        return request_data

    async def get_conversation_completion(
        self,
        messages: List[dict],
        session: RetryClient,
        role: str = "assistant",
        **request_params,
    ) -> dict:
        """
        Query the model a single time with a message.

        :param messages: List of messages to query the model with.
                         Expected format: [{"role": "user", "content": "Hello!"}, ...]
        :type messages: List[dict]
        :param session: aiohttp RetryClient object to query the model with.
        :type session: RetryClient
        :param role: Not used for this model, since it is a chat model.
        :type role: str
        :keyword **request_params: Additional parameters to pass to the model.
        :return: A dictionary representing the completion of the conversation query.
        :rtype: dict
        """
        request_data = self.format_request_data(
            messages=messages,
            **request_params,
        )
        return await self.request_api(
            session=session,
            request_data=request_data,
        )

    async def request_api(
        self,
        session: RetryClient,
        request_data: dict,
    ) -> dict:
        """
        Request the model with a body of data.

        :param session: HTTPS Session for invoking the endpoint.
        :type session: RetryClient
        :param request_data: Prompt dictionary to query the model with. (Pass {"prompt": prompt} instead of prompt.)
        :type request_data: Dict[str, Any]
        :return: A body of data resulting from the model query.
        :rtype: Dict[str, Any]
        """

        self._log_request(request_data)

        token = self.token_manager.get_token()

        proxy_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        }

        headers = {
            "Content-Type": "application/json",
            "X-CV": f"{uuid.uuid4()}",
            "X-ModelType": self.model or "",
        }
        # add all additional headers
        headers.update(self.additional_headers)  # type: ignore[arg-type]

        params = {}
        if self.api_version:
            params["api-version"] = self.api_version

        sim_request_dto = SimulationRequestDTO(
            url=self.endpoint_url,
            headers=headers,
            payload=request_data,
            params=params,
            templatekey=self.tkey,
            template_parameters=self.tparam,
        )

        time_start = time.time()
        full_response = None

        async with session.post(
            url=self.endpoint_url, headers=proxy_headers, json=sim_request_dto.to_dict()
        ) as response:
            if response.status == 202:
                response = await response.json()
                self.result_url = response["location"]
            else:
                raise HTTPException(
                    reason=f"Received unexpected HTTP status: {response.status} {await response.text()}"
                )

        retry_options = JitterRetry(  # set up retry configuration
            statuses=[202],  # on which statuses to retry
            attempts=7,
            start_timeout=10,
            max_timeout=180,
            retry_all_server_errors=False,
        )

        exp_retry_client = AsyncHTTPClientWithRetry(
            n_retry=None,
            retry_timeout=None,
            logger=logging.getLogger(),
            retry_options=retry_options,
        )

        # initial 10 seconds wait before attempting to fetch result
        await asyncio.sleep(10)

        async with exp_retry_client.client as expsession:
            async with expsession.get(url=self.result_url, headers=proxy_headers) as response:
                if response.status == 200:
                    response_data = await response.json()
                    self.logger.info("Response: %s", response_data)

                    # Copy the full response and return it to be saved in jsonl.
                    full_response = copy.copy(response_data)

                    time_taken = time.time() - time_start

                    # pylint: disable=unexpected-keyword-arg
                    parsed_response = self._parse_response(  # type: ignore[call-arg]
                        response_data, request_data=request_data
                    )
                else:
                    raise HTTPException(
                        reason=f"Received unexpected HTTP status: {response.status} {await response.text()}"
                    )

        return {
            "request": request_data,
            "response": parsed_response,
            "time_taken": time_taken,
            "full_response": full_response,
        }
