# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# pylint: skip-file
import asyncio
import copy
import logging
import time
import uuid
from abc import ABC, abstractmethod
from collections import deque
from typing import Deque, Dict, List, Optional, Union
from urllib.parse import urlparse

from promptflow.evals._http_utils import AsyncHttpPipeline

from ._identity_manager import APITokenManager

MIN_ERRORS_TO_FAIL = 3
MAX_TIME_TAKEN_RECORDS = 20_000


def get_model_class_from_url(endpoint_url: str):
    """Convert an endpoint URL to the appropriate model class."""
    endpoint_path = urlparse(endpoint_url).path  # remove query params

    if endpoint_path.endswith("chat/completions"):
        return OpenAIChatCompletionsModel
    elif endpoint_path.endswith("completions"):
        return OpenAICompletionsModel
    else:
        raise ValueError(f"Unknown API type for endpoint {endpoint_url}")


# ===========================================================
# ===================== LLMBase Class =======================
# ===========================================================


class LLMBase(ABC):
    """
    Base class for all LLM models.
    """

    def __init__(self, endpoint_url: str, name: str = "unknown", additional_headers: Optional[dict] = {}):
        self.endpoint_url = endpoint_url
        self.name = name
        self.additional_headers = additional_headers
        self.logger = logging.getLogger(repr(self))

        # Metric tracking
        self._lock = None
        self.response_times: Deque[Union[int, float]] = deque(maxlen=MAX_TIME_TAKEN_RECORDS)
        self.step = 0
        self.error_count = 0

    @property
    async def lock(self):
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    @abstractmethod
    def get_model_params(self) -> dict:
        pass

    @abstractmethod
    def format_request_data(self, prompt: str, **request_params) -> dict:
        pass

    async def get_completion(
        self,
        prompt: str,
        session: AsyncHttpPipeline,
        **request_params,
    ) -> dict:
        """
        Query the model a single time with a prompt.

        Parameters
        ----------
        prompt: Prompt str to query model with.
        session: AsyncHttpPipeline object to use for the request.
        **request_params: Additional parameters to pass to the request.
        """
        request_data = self.format_request_data(prompt, **request_params)
        return await self.request_api(
            session=session,
            request_data=request_data,
        )

    @abstractmethod
    async def get_all_completions(
        self,
        prompts: List[str],
        session: AsyncHttpPipeline,
        api_call_max_parallel_count: int,
        api_call_delay_seconds: float,
        request_error_rate_threshold: float,
        **request_params,
    ) -> List[dict]:
        pass

    @abstractmethod
    async def request_api(
        self,
        session: AsyncHttpPipeline,
        request_data: dict,
    ) -> dict:
        pass

    @abstractmethod
    async def get_conversation_completion(
        self,
        messages: List[dict],
        session: AsyncHttpPipeline,
        role: str,
        **request_params,
    ) -> dict:
        pass

    @abstractmethod
    async def request_api_parallel(
        self,
        request_datas: List[dict],
        output_collector: List,
        session: AsyncHttpPipeline,
        api_call_delay_seconds: float,
        request_error_rate_threshold: float,
    ) -> None:
        pass

    def _log_request(self, request: dict) -> None:
        self.logger.info(f"Request: {request}")

    async def _add_successful_response(self, time_taken: Union[int, float]) -> None:
        async with self.lock:
            self.response_times.append(time_taken)
            self.step += 1

    async def _add_error(self) -> None:
        async with self.lock:
            self.error_count += 1
            self.step += 1

    async def get_response_count(self) -> int:
        async with self.lock:
            return len(self.response_times)

    async def get_response_times(self) -> List[float]:
        async with self.lock:
            return list(self.response_times)

    async def get_average_response_time(self) -> float:
        async with self.lock:
            return sum(self.response_times) / len(self.response_times)

    async def get_error_rate(self) -> float:
        async with self.lock:
            return self.error_count / self.step

    async def get_error_count(self) -> int:
        async with self.lock:
            return self.error_count

    def __repr__(self):
        return f"{self.__class__.__name__}(name={self.name})"


# ===========================================================
# ================== OpenAICompletions ======================
# ===========================================================


class OpenAICompletionsModel(LLMBase):
    """
    Object for calling a Completions-style API for OpenAI models.
    """

    prompt_idx_key = "__prompt_idx__"

    max_stop_tokens = 4
    stop_tokens = ["<|im_end|>", "<|endoftext|>"]

    model_param_names = [
        "model",
        "temperature",
        "max_tokens",
        "top_p",
        "n",
        "frequency_penalty",
        "presence_penalty",
        "stop",
    ]

    CHAT_START_TOKEN = "<|im_start|>"
    CHAT_END_TOKEN = "<|im_end|>"

    def __init__(
        self,
        *,
        endpoint_url: str,
        name: str = "OpenAICompletionsModel",
        additional_headers: Optional[dict] = {},
        api_version: Optional[str] = "2023-03-15-preview",
        token_manager: APITokenManager,
        azureml_model_deployment: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = 0.7,
        max_tokens: Optional[int] = 300,
        top_p: Optional[float] = None,  # Recommended to use top_p or temp, not both
        n: Optional[int] = 1,
        frequency_penalty: Optional[float] = 0,
        presence_penalty: Optional[float] = 0,
        stop: Optional[Union[List[str], str]] = None,
        image_captions: Dict[str, str] = {},
        images_dir: Optional[str] = None,  # Note: unused, kept for class compatibility
    ):
        super().__init__(endpoint_url=endpoint_url, name=name, additional_headers=additional_headers)
        self.api_version = api_version
        self.token_manager = token_manager
        self.azureml_model_deployment = azureml_model_deployment
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.n = n
        self.frequency_penalty = frequency_penalty
        self.presence_penalty = presence_penalty
        self.image_captions = image_captions

        # Default stop to end token if not provided
        if not stop:
            stop = []
        # Else if stop sequence is given as a string (Ex: "["\n", "<im_end>"]"), convert
        elif type(stop) is str and stop.startswith("[") and stop.endswith("]"):
            stop = eval(stop)
        elif type(stop) is str:
            stop = [stop]
        self.stop: List = stop  # type: ignore[assignment]

        # If stop tokens do not include default end tokens, add them
        for token in self.stop_tokens:
            if len(self.stop) >= self.max_stop_tokens:
                break
            if token not in self.stop:
                self.stop.append(token)

        if top_p not in [None, 1.0] and temperature is not None:
            self.logger.warning(
                "Both top_p and temperature are set.  OpenAI advises against using both at the same time."
            )

        self.logger.info(f"Default model settings: {self.get_model_params()}")

    def get_model_params(self):
        return {param: getattr(self, param) for param in self.model_param_names if getattr(self, param) is not None}

    def format_request_data(self, prompt: str, **request_params) -> Dict[str, str]:
        """
        Format the request data for the OpenAI API.
        """
        request_data = {"prompt": prompt, **self.get_model_params()}
        request_data.update(request_params)
        return request_data

    async def get_conversation_completion(
        self,
        messages: List[dict],
        session: AsyncHttpPipeline,
        role: str = "assistant",
        **request_params,
    ) -> dict:
        """
        Query the model a single time with a message.

        Parameters
        ----------
        messages: List of messages to query the model with.
        Expected format: [{"role": "user", "content": "Hello!"}, ...]
        session: AsyncHttpPipeline object to query the model with.
        role: Role of the user sending the message.
        request_params: Additional parameters to pass to the model.
        """
        prompt = []
        for message in messages:
            prompt.append(f"{self.CHAT_START_TOKEN}{message['role']}\n{message['content']}\n{self.CHAT_END_TOKEN}\n")
        prompt_string: str = "".join(prompt)
        prompt_string += f"{self.CHAT_START_TOKEN}{role}\n"

        return await self.get_completion(
            prompt=prompt_string,
            session=session,
            **request_params,
        )

    async def get_all_completions(  # type: ignore[override]
        self,
        prompts: List[Dict[str, str]],
        session: AsyncHttpPipeline,
        api_call_max_parallel_count: int = 1,
        api_call_delay_seconds: float = 0.1,
        request_error_rate_threshold: float = 0.5,
        **request_params,
    ) -> List[dict]:
        """
        Run a batch of prompts through the model and return the results in the order given.

        Parameters
        ----------
        prompts: List of prompts to query the model with.
        session: AsyncHttpPipeline to use for the request.
        api_call_max_parallel_count: Number of parallel requests to make to the API.
        api_call_delay_seconds: Number of seconds to wait between API requests.
        request_error_rate_threshold: Maximum error rate allowed before raising an error.
        request_params: Additional parameters to pass to the API.
        """
        if api_call_max_parallel_count > 1:
            self.logger.info(f"Using {api_call_max_parallel_count} parallel workers to query the API..")

        # Format prompts and tag with index
        request_datas: List[Dict] = []
        for idx, prompt in enumerate(prompts):
            prompt: Dict[str, str] = self.format_request_data(prompt, **request_params)
            prompt[self.prompt_idx_key] = idx  # type: ignore[assignment]
            request_datas.append(prompt)

        # Perform inference
        if len(prompts) == 0:
            return []  # queue is empty

        output_collector: List = []
        tasks = [  # create a set of worker-tasks to query inference endpoint in parallel
            asyncio.create_task(
                self.request_api_parallel(
                    request_datas=request_datas,
                    output_collector=output_collector,
                    session=session,
                    api_call_delay_seconds=api_call_delay_seconds,
                    request_error_rate_threshold=request_error_rate_threshold,
                )
            )
            for _ in range(api_call_max_parallel_count)
        ]

        # Await the completion of all tasks, and propagate any exceptions
        await asyncio.gather(*tasks, return_exceptions=False)
        if len(request_datas):
            raise RuntimeError("All inference tasks were finished, but the queue is not empty")

        # Output results back to the caller
        output_collector.sort(key=lambda x: x[self.prompt_idx_key])
        for output in output_collector:
            output.pop(self.prompt_idx_key)
        return output_collector

    async def request_api_parallel(
        self,
        request_datas: List[dict],
        output_collector: List,
        session: AsyncHttpPipeline,
        api_call_delay_seconds: float = 0.1,
        request_error_rate_threshold: float = 0.5,
    ) -> None:
        """
        Query the model for all prompts given as a list and append the output to output_collector.
        No return value, output_collector is modified in place.
        """
        logger_tasks: List = []  # to await for logging to finish

        while True:  # process data from queue until it"s empty
            try:
                request_data = request_datas.pop()
                prompt_idx = request_data.pop(self.prompt_idx_key)

                try:
                    response = await self.request_api(
                        session=session,
                        request_data=request_data,
                    )
                    await self._add_successful_response(response["time_taken"])
                except Exception as e:
                    response = {
                        "request": request_data,
                        "response": {
                            "finish_reason": "error",
                            "error": str(e),
                        },
                    }
                    await self._add_error()

                    self.logger.exception(f"Errored on prompt #{prompt_idx}")

                    # if we count too many errors, we stop and raise an exception
                    response_count = await self.get_response_count()
                    error_rate = await self.get_error_rate()
                    if response_count >= MIN_ERRORS_TO_FAIL and error_rate >= request_error_rate_threshold:
                        error_msg = (
                            f"Error rate is more than {request_error_rate_threshold:.0%} -- something is broken!"
                        )
                        raise Exception(error_msg)

                response[self.prompt_idx_key] = prompt_idx
                output_collector.append(response)

                # Sleep between consecutive requests to avoid rate limit
                await asyncio.sleep(api_call_delay_seconds)

            except IndexError:  # when the queue is empty, the worker is done
                # wait for logging tasks to finish
                await asyncio.gather(*logger_tasks)
                return

    async def request_api(
        self,
        session: AsyncHttpPipeline,
        request_data: dict,
    ) -> dict:
        """
        Request the model with a body of data.

        Parameters
        ----------
        session: HTTPS Session for invoking the endpoint.
        request_data: Prompt dictionary to query the model with. (Pass {"prompt": prompt} instead of prompt.)
        """

        self._log_request(request_data)

        token = await self.token_manager.get_token()

        headers = {
            "Content-Type": "application/json",
            "X-CV": f"{uuid.uuid4()}",
            "X-ModelType": self.model or "",
        }

        if self.token_manager.auth_header == "Bearer":
            headers["Authorization"] = f"Bearer {token}"
        elif self.token_manager.auth_header == "api-key":
            headers["api-key"] = token
            headers["Authorization"] = "api-key"

        # Update timeout for proxy endpoint
        if self.azureml_model_deployment:
            headers["azureml-model-deployment"] = self.azureml_model_deployment

        # add all additional headers
        if self.additional_headers:
            headers.update(self.additional_headers)

        params = {}
        if self.api_version:
            params["api-version"] = self.api_version

        time_start = time.time()
        full_response = None

        response = await session.post(url=self.endpoint_url, headers=headers, json=request_data, params=params)

        response.raise_for_status()

        response_data = response.json()

        self.logger.info(f"Response: {response_data}")

        # Copy the full response and return it to be saved in jsonl.
        full_response = copy.copy(response_data)

        time_taken = time.time() - time_start

        parsed_response = self._parse_response(response_data, request_data=request_data)

        return {
            "request": request_data,
            "response": parsed_response,
            "time_taken": time_taken,
            "full_response": full_response,
        }

    def _parse_response(self, response_data: dict, request_data: Optional[dict] = None) -> dict:
        # https://platform.openai.com/docs/api-reference/completions
        samples = []
        finish_reason = []
        for choice in response_data["choices"]:
            if "text" in choice:
                samples.append(choice["text"])
            if "finish_reason" in choice:
                finish_reason.append(choice["finish_reason"])

        return {"samples": samples, "finish_reason": finish_reason, "id": response_data["id"]}


# ===========================================================
# ============== OpenAIChatCompletionsModel =================
# ===========================================================


class OpenAIChatCompletionsModel(OpenAICompletionsModel):
    """
    OpenAIChatCompletionsModel is a wrapper around OpenAICompletionsModel that
    formats the prompt for chat completion.
    """

    def __init__(self, name="OpenAIChatCompletionsModel", *args, **kwargs):
        super().__init__(name=name, *args, **kwargs)

    def format_request_data(self, messages: List[dict], **request_params):  # type: ignore[override]
        request_data = {"messages": messages, **self.get_model_params()}
        request_data.update(request_params)
        return request_data

    async def get_conversation_completion(
        self,
        messages: List[dict],
        session: AsyncHttpPipeline,
        role: str = "assistant",
        **request_params,
    ) -> dict:
        """
        Query the model a single time with a message.

        Parameters
        ----------
        messages: List of messages to query the model with.
        Expected format: [{"role": "user", "content": "Hello!"}, ...]
        session: AsyncHttpPipeline object to query the model with.
        role: Not used for this model, since it is a chat model.
        request_params: Additional parameters to pass to the model.
        """
        request_data = self.format_request_data(
            messages=messages,
            **request_params,
        )
        return await self.request_api(
            session=session,
            request_data=request_data,
        )

    async def get_completion(
        self,
        prompt: str,
        session: AsyncHttpPipeline,
        **request_params,
    ) -> dict:
        """
        Query a ChatCompletions model with a single prompt.  Note: entire message will be inserted into a "system" call.

        Parameters
        ----------
        prompt: Prompt str to query model with.
        session: AsyncHttpPipeline object to use for the request.
        **request_params: Additional parameters to pass to the request.
        """
        messages = [{"role": "system", "content": prompt}]

        request_data = self.format_request_data(messages=messages, **request_params)
        return await self.request_api(
            session=session,
            request_data=request_data,
        )

    async def get_all_completions(
        self,
        prompts: List[str],  # type: ignore[override]
        session: AsyncHttpPipeline,
        api_call_max_parallel_count: int = 1,
        api_call_delay_seconds: float = 0.1,
        request_error_rate_threshold: float = 0.5,
        **request_params,
    ) -> List[dict]:
        prompts_list = [{"role": "system", "content": prompt} for prompt in prompts]

        return await super().get_all_completions(
            prompts=prompts_list,
            session=session,
            api_call_max_parallel_count=api_call_max_parallel_count,
            api_call_delay_seconds=api_call_delay_seconds,
            request_error_rate_threshold=request_error_rate_threshold,
            **request_params,
        )

    def _parse_response(self, response_data: dict, request_data: Optional[dict] = None) -> dict:
        # https://platform.openai.com/docs/api-reference/chat
        samples = []
        finish_reason = []

        for choice in response_data["choices"]:
            if "message" in choice and "content" in choice["message"]:
                samples.append(choice["message"]["content"])
            if "message" in choice and "finish_reason" in choice["message"]:
                finish_reason.append(choice["message"]["finish_reason"])

        return {"samples": samples, "finish_reason": finish_reason, "id": response_data["id"]}
