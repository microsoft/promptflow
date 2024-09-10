# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import asyncio
import copy
import json
import time
import uuid
from typing import Dict, List

from azure.core.exceptions import HttpResponseError
from azure.core.pipeline.policies import AsyncRetryPolicy, RetryMode

from promptflow.evals._http_utils import AsyncHttpPipeline, get_async_http_client
from promptflow.evals._user_agent import USER_AGENT

from .models import OpenAIChatCompletionsModel


class SimulationRequestDTO:
    """Simulation Request Data Transfer Object

    :param url: The URL to send the request to.
    :type url: str
    :param headers: The headers to send with the request.
    :type headers: Dict[str, str]
    :param payload: The payload to send with the request.
    :type payload: Dict[str, Any]
    :param params: The parameters to send with the request.
    :type params: Dict[str, str]
    :param template_key: The template key to use for the request.
    :type template_key: str
    :param template_parameters: The template parameters to use for the request.
    :type template_parameters: Dict
    """

    def __init__(self, url, headers, payload, params, templatekey, template_parameters):
        self.url = url
        self.headers = headers
        self.json = json.dumps(payload)
        self.params = params
        self.templatekey = templatekey
        self.templateParameters = template_parameters

    def to_dict(self) -> Dict:
        """Convert the DTO to a dictionary.

        :return: The DTO as a dictionary.
        :rtype: Dict
        """
        if self.templateParameters is not None:
            self.templateParameters = {str(k): str(v) for k, v in self.templateParameters.items()}
        return self.__dict__

    def to_json(self):
        """Convert the DTO to a JSON string.

        :return: The DTO as a JSON string.
        :rtype: str
        """
        return json.dumps(self.__dict__)


class ProxyChatCompletionsModel(OpenAIChatCompletionsModel):
    """A chat completion model that uses a proxy to query the model with a body of data.

    :param name: The name of the model.
    :type name: str
    :param template_key: The template key to use for the request.
    :type template_key: str
    :param template_parameters: The template parameters to use for the request.
    :type template_parameters: Dict
    :keyword args: Additional arguments to pass to the parent class.
    :keyword kwargs: Additional keyword arguments to pass to the parent class.
    """

    def __init__(self, name: str, template_key: str, template_parameters, *args, **kwargs) -> None:
        self.tkey = template_key
        self.tparam = template_parameters
        self.result_url = None

        super().__init__(name=name, *args, **kwargs)

    def format_request_data(self, messages: List[Dict], **request_params) -> Dict:  # type: ignore[override]
        """Format the request data to query the model with.

        :param messages: List of messages to query the model with.
            Expected format: [{"role": "user", "content": "Hello!"}, ...]
        :type messages: List[Dict]
        :keyword request_params: Additional parameters to pass to the model.
        :paramtype request_params: Dict
        :return: The formatted request data.
        :rtype: Dict
        """
        request_data = {"messages": messages, **self.get_model_params()}
        request_data.update(request_params)
        return request_data

    async def get_conversation_completion(
        self,
        messages: List[Dict],
        session: AsyncHttpPipeline,
        role: str = "assistant",  # pylint: disable=unused-argument
        **request_params,
    ) -> dict:
        """
        Query the model a single time with a message.

        :param messages: List of messages to query the model with.
            Expected format: [{"role": "user", "content": "Hello!"}, ...]
        :type messages: List[Dict]
        :param session: AsyncHttpPipeline object to query the model with.
        :type session: ~promptflow.evals._http_utils.AsyncHttpPipeline
        :param role: The role of the user sending the message. This parameter is not used in this method;
            however, it must be included to match the method signature of the parent class. Defaults to "assistant".
        :type role: str
        :keyword request_params: Additional parameters to pass to the model.
        :paramtype request_params: Dict
        :return: A dictionary representing the completion of the conversation query.
        :rtype: Dict
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
        session: AsyncHttpPipeline,
        request_data: dict,
    ) -> dict:
        """
        Request the model with a body of data.

        :param session: HTTPS Session for invoking the endpoint.
        :type session: AsyncHttpPipeline
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

        response = await session.post(url=self.endpoint_url, headers=proxy_headers, json=sim_request_dto.to_dict())

        if response.status_code != 202:
            raise HttpResponseError(
                message=f"Received unexpected HTTP status: {response.status} {await response.text()}", response=response
            )

        response = response.json()
        self.result_url = response["location"]

        retry_policy = AsyncRetryPolicy(  # set up retry configuration
            retry_on_status_codes=[202],  # on which statuses to retry
            retry_total=7,
            retry_backoff_factor=10.0,
            retry_backoff_max=180,
            retry_mode=RetryMode.Exponential,
        )

        exp_retry_client = get_async_http_client().with_policies(retry_policy=retry_policy)

        # initial 15 seconds wait before attempting to fetch result
        # Need to wait both in this thread and in the async thread for some reason?
        # Someone not under a crunch and with better async understandings should dig into this more.
        await asyncio.sleep(15)
        time.sleep(15)

        response = await exp_retry_client.get(  # pylint: disable=too-many-function-args,unexpected-keyword-arg
            self.result_url, headers=proxy_headers
        )

        response.raise_for_status()

        response_data = response.json()
        self.logger.info("Response: %s", response_data)

        # Copy the full response and return it to be saved in jsonl.
        full_response = copy.copy(response_data)

        time_taken = time.time() - time_start

        # pylint: disable=unexpected-keyword-arg
        parsed_response = self._parse_response(response_data, request_data=request_data)  # type: ignore[call-arg]

        return {
            "request": request_data,
            "response": parsed_response,
            "time_taken": time_taken,
            "full_response": full_response,
        }
