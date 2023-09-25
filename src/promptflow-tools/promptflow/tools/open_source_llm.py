import functools
import json
import re
import sys
import time
import urllib.request

from abc import abstractmethod
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional
from urllib.request import HTTPError

from promptflow import ToolProvider, tool
from promptflow.connections import CustomConnection
from promptflow.contracts.types import PromptTemplate
from promptflow.tools.common import render_jinja_template, validate_role
from promptflow.tools.exception import (
    OpenSourceLLMOnlineEndpointError,
    OpenSourceLLMUserError,
    OpenSourceLLMKeyValidationError,
    ChatAPIInvalidRole
)

valid_llama_roles = {"user", "assistant"}
mir_deployment_name_config = "azureml-model-deployment"

def handle_oneline_endpoint_error(max_retries: int = 1, #3,
                                  initial_delay: float = 1,
                                  exponential_base: float = 2):
    def deco_retry(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except HTTPError as e:
                    if i == max_retries - 1:
                        error_message = f"Exception hit calling Oneline Endpoint: {type(e).__name__}: {str(e)}"
                        print(error_message, file=sys.stderr)
                        raise OpenSourceLLMOnlineEndpointError(message=error_message)

                    delay *= exponential_base
                    delay_from_error_message = None
                    final_delay = delay_from_error_message if delay_from_error_message else delay
                    time.sleep(final_delay)
        return wrapper
    return deco_retry


def format_generic_response_payload(output: bytes, response_key: str) -> str:
    response_json = json.loads(output)
    try:
        if response_key is None:
            return response_json[0]
        else:
            return response_json[0][response_key]
    except KeyError as e:
        if response_key is None:
            message = f"""Expected the response to fit the following schema:
                `[
                    <text>
                ]`
                Instead, received {response_json} and access failed at key `{e}`.
                """
        else:
            message = f"""Expected the response to fit the following schema:
                `[
                    {{
                        "{response_key}": <text>
                    }}
                ]`
                Instead, received {response_json} and access failed at key `{e}`.
                """
        raise OpenSourceLLMUserError(message=message)


class ModelFamily(str, Enum):
    LLAMA = "LLaMa"
    DOLLY = "Dolly"
    GPT2 = "GPT-2"
    FALCON = "Falcon"


class API(str, Enum):
    CHAT = "chat"
    COMPLETION = "completion"


class ContentFormatterBase:
    """Transform request and response of AzureML endpoint to match with
    required schema.
    """

    content_type: Optional[str] = "application/json"
    """The MIME type of the input data passed to the endpoint"""

    accepts: Optional[str] = "application/json"
    """The MIME type of the response data returned from the endpoint"""

    @staticmethod
    def escape_special_characters(prompt: str) -> str:
        """Escapes any special characters in `prompt`"""
        return re.sub(
            r'\\([\\\"a-zA-Z])',
            r'\\\1',
            prompt)


    @abstractmethod
    def format_request_payload(self, prompt: str, model_kwargs: Dict) -> str:
        """Formats the request body according to the input schema of
        the model. Returns bytes or seekable file like object in the
        format specified in the content_type request header.
        """

    @abstractmethod
    def format_response_payload(self, output: bytes) -> str:
        """Formats the response body according to the output
        schema of the model. Returns the data type that is
        received from the response.
        """


class GPT2ContentFormatter(ContentFormatterBase):
    """Content handler for LLMs from the OSS catalog."""

    def format_request_payload(self, prompt: str, model_kwargs: Dict) -> str:
        input_str = json.dumps(
            {
                "inputs": {"input_string": [ContentFormatterBase.escape_special_characters(prompt)]},
                "parameters": model_kwargs,
            }
        )
        return input_str

    def format_response_payload(self, output: bytes) -> str:
        return format_generic_response_payload(output, response_key="0")


class HFContentFormatter(ContentFormatterBase):
    """Content handler for LLMs from the HuggingFace catalog."""

    def format_request_payload(self, prompt: str, model_kwargs: Dict) -> str:
        input_str = json.dumps(
            {
                "inputs": [ContentFormatterBase.escape_special_characters(prompt)],
                "parameters": model_kwargs,
            }
        )
        return input_str

    def format_response_payload(self, output: bytes) -> str:
        return format_generic_response_payload(output, response_key="generated_text")


class DollyContentFormatter(ContentFormatterBase):
    """Content handler for the Dolly-v2-12b model"""

    def format_request_payload(self, prompt: str, model_kwargs: Dict) -> str:
        input_str = json.dumps(
            {
                "input_data": {"input_string": [ContentFormatterBase.escape_special_characters(prompt)]},
                "parameters": model_kwargs,
            }
        )
        return input_str

    def format_response_payload(self, output: bytes) -> str:
        return format_generic_response_payload(output, response_key=None)


class LlamaContentFormatter(ContentFormatterBase):
    """Content formatter for LLaMa"""

    def __init__(self, api: API, chat_history: Optional[str] = ""):
        super().__init__()
        self.api = api
        self.chat_history = chat_history

    @staticmethod
    def parse_chat(chat_str: str) -> List[Dict[str, str]]:
        # LLaMa only supports below roles.
        separator = r"(?i)\n*(system|user|assistant)\s*:\s*\n"
        chunks = re.split(separator, chat_str)

        # remove any empty chunks
        chunks = [c.strip() for c in chunks if c.strip()]

        chat_list = []
        for index in range(0, len(chunks), 2):
            role = chunks[index].lower()

            # Check if prompt follows chat api message format and has valid role.
            try:
                validate_role(role, valid_llama_roles)
            except ChatAPIInvalidRole as e:
                raise OpenSourceLLMUserError(message=e.message)

            if len(chunks) <= index + 1:
                raise OpenSourceLLMUserError(message="Unexpected chat format. Please ensure the query matches the chat format of the model used.")
            
            chat_list.append({
                "role": role,
                "content": chunks[index+1]
            })

        return chat_list

    def format_request_payload(self, prompt: str, model_kwargs: Dict) -> str:
        """Formats the request according the the chosen api"""
        if "do_sample" not in model_kwargs:
            model_kwargs["do_sample"] = True

        if self.api == API.CHAT:
            prompt_value = LlamaContentFormatter.parse_chat(self.chat_history)
        else:
            prompt_value = [ContentFormatterBase.escape_special_characters(prompt)]

        return json.dumps(
            {
                "input_data":
                {
                    "input_string": prompt_value, 
                    "parameters": model_kwargs
                }
            }
        )

    def format_response_payload(self, output: bytes) -> str:
        """Formats response"""
        response_json = json.loads(output)

        if self.api == API.CHAT and "output" in response_json:
            return response_json["output"]
        elif self.api == API.COMPLETION and len(response_json) > 0 and "0" in response_json[0]:
            return response_json[0]["0"]
        else:
            error_message = f"Unexpected response format. Response: {response_json}"
            print(error_message, file=sys.stderr)
            raise OpenSourceLLMOnlineEndpointError(message=error_message)


class ContentFormatterFactory:
    """Factory class for supported models"""

    def get_content_formatter(
        model_family: ModelFamily, api: API, chat_history: Optional[List[Dict]] = []
    ) -> ContentFormatterBase:
        if model_family == ModelFamily.LLAMA:
            return LlamaContentFormatter(chat_history=chat_history, api=api)
        elif model_family == ModelFamily.DOLLY:
            return DollyContentFormatter()
        elif model_family == ModelFamily.GPT2:
            return GPT2ContentFormatter()
        elif model_family == ModelFamily.FALCON:
            return HFContentFormatter()


class AzureMLOnlineEndpoint:
    """Azure ML Online Endpoint models.

    Example:
        .. code-block:: python

            azure_llm = AzureMLModel(
                endpoint_url="https://<your-endpoint>.<your_region>.inference.ml.azure.com/score",
                endpoint_api_key="my-api-key",
                content_formatter=content_formatter,
            )
    """  # noqa: E501

    endpoint_url: str = ""
    """URL of pre-existing Endpoint. Should be passed to constructor or specified as
        env var `AZUREML_ENDPOINT_URL`."""

    endpoint_api_key: str = ""
    """Authentication Key for Endpoint. Should be passed to constructor or specified as
        env var `AZUREML_ENDPOINT_API_KEY`."""

    content_formatter: Any = None
    """The content formatter that provides an input and output
    transform function to handle formats between the LLM and
    the endpoint"""

    model_kwargs: Optional[Dict] = None
    """Key word arguments to pass to the model."""

    def __init__(
        self,
        endpoint_url: str,
        endpoint_api_key: str,
        content_formatter: ContentFormatterBase,
        model_kwargs: Optional[Dict] = None,
    ):
        self.endpoint_url = endpoint_url
        self.endpoint_api_key = endpoint_api_key
        self.content_formatter = content_formatter
        self.model_kwargs = model_kwargs

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """Get the identifying parameters."""
        _model_kwargs = self.model_kwargs or {}
        return {
            **{"model_kwargs": _model_kwargs},
        }

    @property
    def _llm_type(self) -> str:
        """Return type of llm."""
        return "azureml_endpoint"

    def _call_endpoint(self, body: bytes) -> bytes:
        """call."""

        headers = {"Content-Type": "application/json", "Authorization": ("Bearer " + self.endpoint_api_key)}

        # If this is not set it'll use the default deployment on the endpoint.
        if mir_deployment_name_config in self.model_kwargs:
            headers[mir_deployment_name_config] = self.model_kwargs[mir_deployment_name_config]
            del self.model_kwargs[mir_deployment_name_config]

        req = urllib.request.Request(self.endpoint_url, body, headers)
        response = urllib.request.urlopen(req, timeout=50)
        result = response.read()
        return result

    def __call__(
        self,
        prompt: str
    ) -> str:
        """Call out to an AzureML Managed Online endpoint.
        Args:
            prompt: The prompt to pass into the model.
            stop: Optional list of stop words to use when generating.
        Returns:
            The string generated by the model.
        Example:
            .. code-block:: python
                response = azureml_model("Tell me a joke.")
        """
        _model_kwargs = self.model_kwargs or {}

        body = self.content_formatter.format_request_payload(prompt, _model_kwargs)
        endpoint_request = str.encode(body)
        endpoint_response = self._call_endpoint(endpoint_request)
        response = self.content_formatter.format_response_payload(endpoint_response)
        return response


class OpenSourceLLM(ToolProvider):
    REQUIRED_CONFIG_KEYS = ["endpoint_url", "model_family"]
    REQUIRED_SECRET_KEYS = ["endpoint_api_key"]

    def __init__(self, connection: CustomConnection):
        super().__init__()

        conn_dict = dict(connection)
        for key in self.REQUIRED_CONFIG_KEYS:
            if key not in conn_dict:
                accepted_keys = ",".join([key for key in self.REQUIRED_CONFIG_KEYS])
                raise OpenSourceLLMKeyValidationError(
                    message=f"""Required key `{key}` not found in given custom connection.
                      Required keys are: {accepted_keys}."""
                )
        for key in self.REQUIRED_SECRET_KEYS:
            if key not in conn_dict:
                accepted_keys = ",".join([key for key in self.REQUIRED_SECRET_KEYS])
                raise OpenSourceLLMKeyValidationError(
                    message=f"""Required secret key `{key}` not found in given custom connection.
                      Required keys are: {accepted_keys}."""
                )
        try:
            self.model_family = ModelFamily[connection.configs['model_family']]
        except KeyError:
            accepted_models = ",".join([model.name for model in ModelFamily])
            raise OpenSourceLLMKeyValidationError(
                message=f"""Given model_family '{connection.configs['model_family']}' not recognized.
                  Supported models are: {accepted_models}."""
            )
        self.connection = connection

    @tool
    @handle_oneline_endpoint_error()
    def call(
        self,
        prompt: PromptTemplate,
        api: API,
        model_kwargs: Optional[Dict] = {},
        **kwargs
    ) -> str:
        prompt = render_jinja_template(prompt, trim_blocks=True, keep_trailing_newline=True, **kwargs)

        content_formatter = ContentFormatterFactory.get_content_formatter(
            model_family=self.model_family,
            api=api,
            chat_history=prompt
        )

        llm = AzureMLOnlineEndpoint(
            endpoint_url=self.connection.configs['endpoint_url'],
            endpoint_api_key=self.connection.secrets['endpoint_api_key'],
            content_formatter=content_formatter,
            model_kwargs=model_kwargs
        )

        def _do_llm(llm: AzureMLOnlineEndpoint, prompt: str) -> str:
            return llm(prompt)

        return _do_llm(llm, prompt)
