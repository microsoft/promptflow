import functools
import json
import os
import re
import sys
import time
import urllib.request

from abc import abstractmethod
from enum import Enum
from typing import Any, Dict, List, Tuple, Mapping, Optional, Union
from urllib.request import HTTPError

from promptflow._core.tool import ToolProvider, tool
from promptflow._sdk._constants import ConnectionType
from promptflow.connections import CustomConnection
from promptflow.contracts.types import PromptTemplate
from promptflow.tools.common import render_jinja_template, validate_role
from promptflow.tools.exception import (
    OpenSourceLLMOnlineEndpointError,
    OpenSourceLLMUserError,
    OpenSourceLLMKeyValidationError,
    ChatAPIInvalidRole
)

VALID_LLAMA_ROLES = {"system", "user", "assistant"}
REQUIRED_CONFIG_KEYS = ["endpoint_url", "model_family"]
REQUIRED_SECRET_KEYS = ["endpoint_api_key"]
ENDPOINT_REQUIRED_ENV_VARS = ["AZUREML_ARM_SUBSCRIPTION", "AZUREML_ARM_RESOURCEGROUP", "AZUREML_ARM_WORKSPACE_NAME"]


def handle_online_endpoint_error(max_retries: int = 3,
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
                        error_message = f"Exception hit calling Online Endpoint: {type(e).__name__}: {str(e)}"
                        print(error_message, file=sys.stderr)
                        raise OpenSourceLLMOnlineEndpointError(message=error_message)

                    delay *= exponential_base
                    time.sleep(delay)
        return wrapper
    return deco_retry


class Endpoint:
    def __init__(self,
                 endpoint_name: str,
                 endpoint_url: str,
                 endpoint_key: str):
        self.deployments: List[Deployment] = []
        self.default_deployment: Deployment = None
        self.endpoint_url = endpoint_url
        self.endpoint_key = endpoint_key
        self.endpoint_name = endpoint_name


class Deployment:
    def __init__(self,
                 deployment_name: str,
                 model_family: str):
        self.model_family = model_family
        self.deployment_name = deployment_name


class ServerlessEndpointsContainer:
    API_VERSION = "2023-08-01-preview"

    def _get_headers(self):
        from azure.identity import DefaultAzureCredential
        credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)
        token = credential.get_token("https://management.azure.com/.default").token
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        return headers

    def get_serverless_arm_url(self, subscription_id, resource_group, workspace_name, suffix=None):
        suffix = "" if suffix is None else f"/{suffix}"
        return f"https://management.azure.com/subscriptions/{subscription_id}" \
            + f"/resourceGroups/{resource_group}/providers/Microsoft.MachineLearningServices" \
            + f"/workspaces/{workspace_name}/serverlessEndpoints{suffix}?api-version={self.API_VERSION}"

    def _list(self, subscription_id, resource_group, workspace_name):
        try:
            headers = self._get_headers()
        except Exception as e:
            print(f"Unable to get token for ARM. Skipping serverless endpoints. Exception: {e}", file=sys.stderr)
            return []
        url = self.get_serverless_arm_url(subscription_id, resource_group, workspace_name)

        try:
            req = urllib.request.Request(url=url, headers=headers)
            response = urllib.request.urlopen(req, timeout=50)
            result = response.read()
            return json.loads(result)['value']
        except Exception as e:
            print(f"Error encountered when listing serverless endpoints. Exception: {e}", file=sys.stderr)
            return []

    def _validate_model_family(self, serverless_endpoint):
        try:
            if (serverless_endpoint.get('properties', {}).get('offer', {}).get('publisher') == 'Meta'
                and "llama" in serverless_endpoint.get('properties', {}).get('offer', {}).get('offerName')
                and serverless_endpoint.get('properties', {}).get('provisioningState') == "Succeeded"):
                return ModelFamily.LLAMA
        except Exception as ex:
            print(f"Ignoring endpoint {serverless_endpoint['id']} due to error: {ex}")
            return None

    def list_serverless_endpoints(self, subscription_id, resource_group, workspace_name):
        serverlessEndpoints = self._list(subscription_id, resource_group, workspace_name)

        result = []
        for e in serverlessEndpoints:
            if (self._validate_model_family(e)):
                result.append({
                    "value": f"serverlessEndpoint/{e['name']}",
                    "display_value": f"[Serverless] {e['name']}",
                    # "hyperlink": self.get_endpoint_url(e.endpoint_name)
                    "description": f"Serverless Endpoint:  {e['name']}",
                })

        return result

    def _list_endpoint_key(self, subscription_id, resource_group, workspace_name, serverless_endpoint_name):
        try:
            headers = self._get_headers()
        except Exception as e:
            print(f"Unable to get token for ARM. Exception: {e}", file=sys.stderr)
            raise

        url = self.get_serverless_arm_url(subscription_id,
                                          resource_group,
                                          workspace_name,
                                          f"{serverless_endpoint_name}/listKeys")
        try:
            req = urllib.request.Request(url=url, data=str.encode(""), headers=headers)
            response = urllib.request.urlopen(req, timeout=50)
            result = response.read()
            return json.loads(result)
        except Exception as e:
            print(f"Unable to get key from selected serverless endpoint. Exception: {e}", file=sys.stderr)

    def get_serverless_endpoint(self, subscription_id, resource_group, workspace_name, serverless_endpoint_name):
        try:
            headers = self._get_headers()
        except Exception as e:
            print(f"Unable to get token for ARM. Exception: {e}", file=sys.stderr)
            raise
        url = self.get_serverless_arm_url(subscription_id, resource_group, workspace_name, serverless_endpoint_name)

        try:
            req = urllib.request.Request(url=url, headers=headers)
            response = urllib.request.urlopen(req, timeout=50)
            result = response.read()
            return json.loads(result)
        except Exception as e:
            print(f"Unable to get selected serverless endpoint. Exception: {e}", file=sys.stderr)

    def get_serverless_endpoint_key(self,
                                    subscription_id,
                                    resource_group,
                                    workspace_name,
                                    serverless_endpoint_name) -> Tuple[str, str, str]:
        endpoint = self.get_serverless_endpoint(subscription_id,
                                                resource_group,
                                                workspace_name,
                                                serverless_endpoint_name)
        endpoint_url = endpoint.get('properties', {}).get('inferenceEndpoint', {}).get('uri')
        model_family = self._validate_model_family(endpoint)
        endpoint_key = self._list_endpoint_key(subscription_id,
                                               resource_group,
                                               workspace_name,
                                               serverless_endpoint_name)['primaryKey']
        return (endpoint_url,
                endpoint_key,
                model_family)


class CustomConnectionsContainer:
    def __init__(self) -> None:
        self.__azure_custom_connections = None
        self.__subscription_id = None
        self.__resource_group_name = None
        self.__workspace_name = None

    def get_azure_custom_connection_names(self,
                                          subscription_id,
                                          resource_group_name,
                                          workspace_name) -> List[Dict[str, Union[str, int, float, list, Dict]]]:

        if (self.__azure_custom_connections is not None
                and self.__subscription_id == subscription_id
                and self.__resource_group_name == resource_group_name
                and self.__workspace_name == workspace_name):
            return self.__azure_custom_connections

        result = []
        try:
            from azure.identity import DefaultAzureCredential
            from promptflow.azure import PFClient as AzurePFClient
            credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)
        except Exception as e:
            print(f"Skipping Azure PFClient. Exception: {e}", file=sys.stderr)
            return result

        try:
            azure_pf_client = AzurePFClient(
                credential=credential,
                subscription_id=subscription_id,
                resource_group_name=resource_group_name,
                workspace_name=workspace_name)
        except Exception:
            message = "Skipping Azure PFClient. To connect, please ensure the following environment variables are set: "
            message += ",".join(ENDPOINT_REQUIRED_ENV_VARS)
            print(message, file=sys.stderr)
            return result

        connections = azure_pf_client._connections.list()

        for c in connections:
            if c.type == ConnectionType.CUSTOM and "model_family" in c.configs:
                try:
                    validate_model_family(c.configs["model_family"])
                    result.append({
                        "value": f"connection/{c.name}",
                        "display_value": f"[Connection] {c.name}",
                        # "hyperlink": "",
                        "description": f"Custom Connection:  {c.name}",
                    })

                except Exception:
                    # silently ignore unsupported model family
                    continue

        self.__subscription_id = subscription_id
        self.__resource_group_name = resource_group_name
        self.__workspace_name = workspace_name
        self.__azure_custom_connections = result

        return result

    def get_local_custom_connection_names(self) -> List[Dict[str, Union[str, int, float, list, Dict]]]:
        result = []
        try:
            from promptflow import PFClient as LocalPFClient
        except Exception as e:
            print(f"Skipping Local PFClient. Exception: {e}", file=sys.stderr)
            return result

        pf = LocalPFClient()
        connections = pf.connections.list()

        for c in connections:
            if c.type == ConnectionType.CUSTOM and "model_family" in c.configs:
                try:
                    validate_model_family(c.configs["model_family"])
                    result.append({
                        "value": f"localConnection/{c.name}",
                        "display_value": f"[Local Connection] {c.name}",
                        # "hyperlink": "",
                        "description": f"Local Custom Connection:  {c.name}",
                    })

                except Exception:
                    # silently ignore unsupported model family
                    continue

        return result

    def get_endpoint_from_local_custom_connection(self, connection_name) -> Tuple[str, str, str]:
        from promptflow import PFClient as LocalPFClient
        pf = LocalPFClient()

        connection = pf.connections.get(connection_name, with_secrets=True)

        return self.get_endpoint_from_custom_connection(connection)

    def get_endpoint_from_azure_custom_connection(self,
                                                  subscription_id,
                                                  resource_group_name,
                                                  workspace_name,
                                                  connection_name) -> Tuple[str, str, str]:
        from promptflow.azure import PFClient as AzurePFClient
        from azure.identity import DefaultAzureCredential
        credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)

        azure_pf_client = AzurePFClient(
                credential=credential,
                subscription_id=subscription_id,
                resource_group_name=resource_group_name,
                workspace_name=workspace_name)

        connection = azure_pf_client._arm_connections.get(connection_name)

        return self.get_endpoint_from_custom_connection(connection)

    def get_endpoint_from_custom_connection(self, connection: CustomConnection) -> Tuple[str, str, str]:
        conn_dict = dict(connection)
        for key in REQUIRED_CONFIG_KEYS:
            if key not in conn_dict:
                accepted_keys = ",".join([key for key in REQUIRED_CONFIG_KEYS])
                raise OpenSourceLLMKeyValidationError(
                    message=f"""Required key `{key}` not found in given custom connection.
Required keys are: {accepted_keys}."""
                )

        for key in REQUIRED_SECRET_KEYS:
            if key not in conn_dict:
                accepted_keys = ",".join([key for key in REQUIRED_SECRET_KEYS])
                raise OpenSourceLLMKeyValidationError(
                    message=f"""Required secret key `{key}` not found in given custom connection.
Required keys are: {accepted_keys}."""
                )

        model_family = validate_model_family(connection.configs['model_family'])

        return (connection.configs['endpoint_url'],
                connection.secrets['endpoint_api_key'],
                model_family)

    def list_custom_connection_names(self,
                                     subscription_id: str,
                                     resource_group_name: str,
                                     workspace_name: str) -> List[Dict[str, Union[str, int, float, list, Dict]]]:

        azure_custom_connections = self.get_azure_custom_connection_names(subscription_id,
                                                                          resource_group_name,
                                                                          workspace_name)
        local_custom_connections = self.get_local_custom_connection_names()

        return azure_custom_connections + local_custom_connections


class EndpointsContainer:
    def __init__(self) -> None:
        self.__endpoints_and_deployments = None
        self.__subscription_id = None
        self.__resource_group_name = None
        self.__workspace_name = None

    def get_ml_client(self,
                      subscription_id: str,
                      resource_group_name: str,
                      workspace_name: str):
        from azure.ai.ml import MLClient
        from azure.identity import DefaultAzureCredential
        credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)
        try:
            return MLClient(
                credential=credential,
                subscription_id=subscription_id,
                resource_group_name=resource_group_name,
                workspace_name=workspace_name)
        except Exception as e:
            message = "Unable to connect to AzureML. Please ensure the following environment variables are set: "
            message += ",".join(ENDPOINT_REQUIRED_ENV_VARS)
            message += "\nException: " + str(e)
            raise OpenSourceLLMOnlineEndpointError(message=message)

    def get_endpoints_and_deployments(self,
                                      subscription_id: str,
                                      resource_group_name: str,
                                      workspace_name: str) -> List[Endpoint]:

        if (self.__endpoints_and_deployments is not None
                and self.__subscription_id == subscription_id
                and self.__resource_group_name == resource_group_name
                and self.__workspace_name == workspace_name):
            return self.__endpoints_and_deployments

        ml_client = self.get_ml_client(subscription_id, resource_group_name, workspace_name)
        self.__subscription_id = subscription_id
        self.__resource_group_name = resource_group_name
        self.__workspace_name = workspace_name

        list_of_endpoints: List[Endpoint] = []

        for ep in ml_client.online_endpoints.list():
            endpoint = Endpoint(
                endpoint_name=ep.name,
                endpoint_url=ep.scoring_uri,
                endpoint_key=ml_client.online_endpoints.get_keys(ep.name).primary_key)

            ordered_deployment_names = sorted(ep.traffic, key=lambda item: item[1])
            deployments = ml_client.online_deployments.list(ep.name)

            for deployment_name in ordered_deployment_names:
                for d in deployments:
                    if d.name == deployment_name:
                        model_family = get_model_type(d.model)

                        if model_family is None:
                            continue

                        deployment = Deployment(deployment_name=d.name, model_family=model_family)
                        endpoint.deployments.append(deployment)

                        # Deployment are ordered by traffic level, first in is default
                        if endpoint.default_deployment is None:
                            endpoint.default_deployment = deployment

            if len(endpoint.deployments) > 0:
                list_of_endpoints.append(endpoint)

        self.__endpoints_and_deployments = list_of_endpoints
        return self.__endpoints_and_deployments

    def get_endpoint_url(self, endpoint_name, subscription_id, resource_group_name, workspace_name):
        return f"https://ml.azure.com/endpoints/realtime/{endpoint_name}" \
            + f"/detail?wsid=/subscriptions/{subscription_id}" \
            + f"/resourceGroups/{resource_group_name}" \
            + f"/providers/Microsoft.MachineLearningServices/workspaces/{workspace_name}"

    def list_endpoint_names(self,
                            subscription_id,
                            resource_group_name,
                            workspace_name
                            ) -> List[Dict[str, Union[str, int, float, list, Dict]]]:
        '''Function for listing endpoints in the UX'''
        endpoints_and_deployments = self.get_endpoints_and_deployments(
            subscription_id,
            resource_group_name,
            workspace_name)

        result = []
        for e in endpoints_and_deployments:
            result.append({
                "value": f"onlineEndpoint/{e.endpoint_name}",
                "display_value": f"[Online] {e.endpoint_name}",
                "hyperlink": self.get_endpoint_url(e.endpoint_name,
                                                   subscription_id,
                                                   resource_group_name,
                                                   workspace_name),
                "description": f"Online Endpoint:  {e.endpoint_name}",
            })
        return result

    def list_deployment_names(self,
                              subscription_id,
                              resource_group_name,
                              workspace_name,
                              endpoint_name: str
                              ) -> List[Dict[str, Union[str, int, float, list, Dict]]]:
        '''Function for listing deployments in the UX'''
        if endpoint_name is None:
            return []

        endpoints_and_deployments = self.get_endpoints_and_deployments(
            subscription_id,
            resource_group_name,
            workspace_name)
        for endpoint in endpoints_and_deployments:
            if endpoint.endpoint_name == endpoint_name:
                result = []
                for d in endpoint.deployments:
                    result.append({
                        "value": d.deployment_name,
                        "display_value": d.deployment_name,
                        # "hyperlink": '',
                        "description": f"this is {d.deployment_name} item",
                    })
                return result
        return []


ENDPOINT_CONTAINER = EndpointsContainer()
CUSTOM_CONNECTION_CONTAINER = CustomConnectionsContainer()
SERVERLESS_ENDPOINT_CONTAINER = ServerlessEndpointsContainer()


def parse_endpoint_connection_type(endpoint_connection_name: str) -> Tuple[str, str]:
    endpoint_connection_details = endpoint_connection_name.split("/")
    return (endpoint_connection_details[0].lower(), endpoint_connection_details[1])


def list_endpoint_names(subscription_id: str,
                        resource_group_name: str,
                        workspace_name: str) -> List[Dict[str, Union[str, int, float, list, Dict]]]:
    serverless_endpoints = SERVERLESS_ENDPOINT_CONTAINER.list_serverless_endpoints(subscription_id,
                                                                                   resource_group_name,
                                                                                   workspace_name)
    online_endpoints = ENDPOINT_CONTAINER.list_endpoint_names(subscription_id, resource_group_name, workspace_name)
    custom_connections = CUSTOM_CONNECTION_CONTAINER.list_custom_connection_names(subscription_id,
                                                                                  resource_group_name,
                                                                                  workspace_name)

    return serverless_endpoints + online_endpoints + custom_connections


def list_deployment_names(subscription_id: str,
                          resource_group_name: str,
                          workspace_name: str,
                          endpoint: str = None) -> List[Dict[str, Union[str, int, float, list, Dict]]]:

    if endpoint is None or endpoint.strip() == "" or "/" not in endpoint:
        return []

    (endpoint_connection_type, endpoint_connection_name) = parse_endpoint_connection_type(endpoint)

    if endpoint_connection_type == "onlineendpoint":
        return ENDPOINT_CONTAINER.list_deployment_names(
            subscription_id,
            resource_group_name,
            workspace_name,
            endpoint_connection_name
        )
    else:
        return []


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


def get_model_type(deployment_model: str) -> str:
    m = re.match(r'azureml://registries/[^/]+/models/([^/]+)/versions/', deployment_model)
    if m is None:
        raise ValueError(f"Unexpected model format: {deployment_model}")
    model = m[1].lower()
    if model.startswith("llama-2"):
        return ModelFamily.LLAMA
    elif model.startswith("tiiuae-falcon"):
        return ModelFamily.FALCON
    elif model.startswith("databricks-dolly-v2"):
        return ModelFamily.DOLLY
    elif model.startswith("gpt2"):
        return ModelFamily.GPT2
    else:
        # Not found and\or handled. Ignore this endpoint\deployment
        return None


def validate_model_family(model_family: str):
    try:
        return ModelFamily[model_family]
    except KeyError:
        accepted_models = ",".join([model.name for model in ModelFamily])
        raise OpenSourceLLMKeyValidationError(
            message=f"""Given model_family '{model_family}' not recognized.
Supported models are: {accepted_models}."""
        )


class ModelFamily(str, Enum):
    LLAMA = "LLaMa"
    DOLLY = "Dolly"
    GPT2 = "GPT-2"
    FALCON = "Falcon"

    @classmethod
    def _missing_(cls, value):
        value = value.lower()
        for member in cls:
            if member.lower() == value:
                return member
        return None


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
                validate_role(role, VALID_LLAMA_ROLES)
            except ChatAPIInvalidRole as e:
                raise OpenSourceLLMUserError(message=e.message)

            if len(chunks) <= index + 1:
                message = "Unexpected chat format. Please ensure the query matches the chat format of the model used."
                raise OpenSourceLLMUserError(message=message)

            chat_list.append({
                "role": role,
                "content": chunks[index+1]
            })

        return chat_list

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

    def format_request_payload(self, prompt: str, model_kwargs: Dict) -> str:
        """Formats the request according the the chosen api"""
        if "do_sample" not in model_kwargs:
            model_kwargs["do_sample"] = True

        if self.api == API.CHAT:
            prompt_value = ContentFormatterBase.parse_chat(self.chat_history)
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


class ServerlessLlamaContentFormatter(ContentFormatterBase):
    """Content formatter for LLaMa"""

    def __init__(self, api: API, chat_history: Optional[str] = ""):
        super().__init__()
        self.api = api
        self.chat_history = chat_history
        self.model_id = "llama-2-7b-hf"

    def format_request_payload(self, prompt: str, model_kwargs: Dict) -> str:
        """Formats the request according the the chosen api"""
        # Modify max_tokens key for serverless
        model_kwargs["max_tokens"] = model_kwargs["max_new_tokens"]
        if self.api == API.CHAT:
            messages = ContentFormatterBase.parse_chat(self.chat_history)
            base_body = {
                "model": self.model_id,
                "messages": messages,
                "n": 1,
            }
            base_body.update(model_kwargs)

        else:
            prompt_value = [ContentFormatterBase.escape_special_characters(prompt)]
            base_body = {
                "model": self.model_id,
                "prompt": prompt_value,
                "n": 1,
            }
            base_body.update(model_kwargs)

        return json.dumps(base_body)

    def format_response_payload(self, output: bytes) -> str:
        """Formats response"""
        response_json = json.loads(output)
        if self.api == API.CHAT and "choices" in response_json:
            return response_json["choices"][0]["message"]["content"]
        elif self.api == API.COMPLETION and "choices" in response_json:
            return response_json["choices"][0]["text"]
        else:
            error_message = f"Unexpected response format. Response: {response_json}"
            print(error_message, file=sys.stderr)
            raise OpenSourceLLMOnlineEndpointError(message=error_message)


class ContentFormatterFactory:
    """Factory class for supported models"""

    def get_content_formatter(
        model_family: ModelFamily, api: API, chat_history: Optional[List[Dict]] = [], endpoint_url: Optional[str] = ""
    ) -> ContentFormatterBase:
        if model_family == ModelFamily.LLAMA:
            if "serverless.ml.azure.com" in endpoint_url:
                return ServerlessLlamaContentFormatter(chat_history=chat_history, api=api)
            else:
                return LlamaContentFormatter(chat_history=chat_history, api=api)
        elif model_family == ModelFamily.DOLLY:
            return DollyContentFormatter()
        elif model_family == ModelFamily.GPT2:
            return GPT2ContentFormatter()
        elif model_family == ModelFamily.FALCON:
            return HFContentFormatter()


class AzureMLOnlineEndpoint:
    """Azure ML Online Endpoint models."""

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
        model_family: ModelFamily,
        deployment_name: Optional[str] = None,
        model_kwargs: Optional[Dict] = None,
    ):
        self.endpoint_url = endpoint_url
        self.endpoint_api_key = endpoint_api_key
        self.deployment_name = deployment_name
        self.content_formatter = content_formatter
        self.model_kwargs = model_kwargs
        self.model_family = model_family

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

        headers = {
            "Content-Type": "application/json",
            "Authorization": ("Bearer " + self.endpoint_api_key),
            "x-ms-user-agent": "PromptFlow/OpenSourceLLM/" + self.model_family}

        # If this is not set it'll use the default deployment on the endpoint.
        if self.deployment_name is not None:
            headers["azureml-model-deployment"] = self.deployment_name

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

    def __init__(self):
        super().__init__()

    def get_deployment_from_endpoint(self,
                                     subscription_id: str,
                                     resource_group_name: str,
                                     workspace_name: str,
                                     endpoint_name: str,
                                     deployment_name: str = None) -> Tuple[str, str, str]:
        endpoints_and_deployments = ENDPOINT_CONTAINER.get_endpoints_and_deployments(
            subscription_id,
            resource_group_name,
            workspace_name)

        for ep in endpoints_and_deployments:
            if ep.endpoint_name == endpoint_name:
                if deployment_name is None:
                    return (ep.endpoint_url,
                            ep.endpoint_key,
                            ep.default_deployment.model_family)
                for d in ep.deployments:
                    if d.deployment_name == deployment_name:
                        return (ep.endpoint_url,
                                ep.endpoint_key,
                                d.model_family)

        message = """Invalid endpoint and deployment values.
Please ensure endpoint name and deployment names are correct, and the deployment was successfull."""
        raise OpenSourceLLMUserError(message=message)

    def sanitize_endpoint_url(self,
                              endpoint_url: str,
                              api_type: API):
        if "serverless.ml.azure.com" in endpoint_url:
            if api_type == API.CHAT:
                if not endpoint_url.endswith("/v1/chat/completions"):
                    return endpoint_url + "/v1/chat/completions"
            else:
                if not endpoint_url.endswith("/v1/completions"):
                    return endpoint_url + "/v1/completions"
        return endpoint_url

    def get_endpoint_details(self,
                             subscription_id: str,
                             resource_group_name: str,
                             workspace_name: str,
                             endpoint: str,
                             api_type: API,
                             deployment_name: str = None) -> Tuple[str, str, str]:

        (endpoint_connection_type, endpoint_connection_name) = parse_endpoint_connection_type(endpoint)

        print(f"endpoint_connection_type: {endpoint_connection_type} name: {endpoint_connection_name}")

        if endpoint_connection_type.lower() == "serverlessendpoint":
            (endpoint_url, endpoint_key, model_family) = SERVERLESS_ENDPOINT_CONTAINER.get_serverless_endpoint_key(
                                                                                                                subscription_id,
                                                                                                                resource_group_name,
                                                                                                                workspace_name,
                                                                                                                endpoint_connection_name)
        elif endpoint_connection_type.lower() == "onlineendpoint":
            (endpoint_url, endpoint_key, model_family) = self.get_deployment_from_endpoint(subscription_id,
                                                                                           resource_group_name,
                                                                                           workspace_name,
                                                                                           endpoint_connection_name,
                                                                                           deployment_name)
        elif endpoint_connection_type.lower() == "connection":
            (endpoint_url, endpoint_key, model_family) = CUSTOM_CONNECTION_CONTAINER.get_endpoint_from_azure_custom_connection(
                                                                                                                    subscription_id,
                                                                                                                    resource_group_name,
                                                                                                                    workspace_name,
                                                                                                                    endpoint_connection_name)
        elif endpoint_connection_type.lower() == "localconnection":
            (endpoint_url, endpoint_key, model_family) = CUSTOM_CONNECTION_CONTAINER.get_endpoint_from_local_custom_connection(
                                                                                                                    endpoint_connection_name)
        else:
            raise OpenSourceLLMUserError(message=f"Invalid endpoint connection type: {endpoint_connection_type}")
        return (self.sanitize_endpoint_url(endpoint_url, api_type), endpoint_key, model_family)

    @tool
    @handle_online_endpoint_error()
    def call(
        self,
        prompt: PromptTemplate,
        api: API,
        endpoint: str = None,
        deployment_name: str = None,
        temperature: float = 1.0,
        max_new_tokens: int = 500,
        top_p: float = 1.0,
        model_kwargs: Optional[Dict] = {},
        **kwargs
    ) -> str:

        # Sanitize deployment name. Empty deployment name is the same as None.
        if deployment_name is not None:
            deployment_name = None if not deployment_name.strip() else deployment_name

        print(f"Executing Open Source LLM Tool for endpoint: '{endpoint}', deployment: '{deployment_name}'")

        (self.endpoint_uri,
            self.endpoint_key,
            self.model_family) = self.get_endpoint_details(
                subscription_id=os.getenv("AZUREML_ARM_SUBSCRIPTION", None),
                resource_group_name=os.getenv("AZUREML_ARM_RESOURCEGROUP", None),
                workspace_name=os.getenv("AZUREML_ARM_WORKSPACE_NAME", None),
                endpoint=endpoint,
                api_type=api,
                deployment_name=deployment_name)

        prompt = render_jinja_template(prompt, trim_blocks=True, keep_trailing_newline=True, **kwargs)

        model_kwargs["top_p"] = top_p
        model_kwargs["temperature"] = temperature
        model_kwargs["max_new_tokens"] = max_new_tokens

        content_formatter = ContentFormatterFactory.get_content_formatter(
            model_family=self.model_family,
            api=api,
            chat_history=prompt,
            endpoint_url=self.endpoint_uri
        )

        llm = AzureMLOnlineEndpoint(
            endpoint_url=self.endpoint_uri,
            endpoint_api_key=self.endpoint_key,
            model_family=self.model_family,
            content_formatter=content_formatter,
            deployment_name=deployment_name,
            model_kwargs=model_kwargs
        )

        return llm(prompt)
