from dataclasses import dataclass
from typing import Union

from promptflow._constants import ConnectionType
from promptflow.core._errors import InvalidConnectionError


class ModelConfiguration:
    pass


@dataclass
class AzureOpenAIModelConfiguration(ModelConfiguration):
    azure_deployment: str
    azure_endpoint: str = None
    api_version: str = None
    api_key: str = None
    organization: str = None
    # connection and model configs are exclusive.
    connection: str = None

    def __post_init__(self):
        self._type = ConnectionType.AZURE_OPEN_AI
        if (
            any([self.azure_endpoint, self.api_key, self.api_version, self.azure_ad_token_provider, self.organization])
            and self.connection
        ):
            raise InvalidConnectionError("Cannot configure model config and connection at the same time.")


@dataclass
class OpenAIModelConfiguration(ModelConfiguration):
    model: str
    base_url: str = None
    api_key: str = None
    organization: str = None
    # connection and model configs are exclusive.
    connection: str = None

    def __post_init__(self):
        self._type = ConnectionType.OPEN_AI
        if any([self.base_url, self.api_key, self.api_version, self.organization]) and self.connection:
            raise InvalidConnectionError("Cannot configure model config and connection at the same time.")


@dataclass
class PromptyModelConfiguration:
    """
    A dataclass that represents a model config of prompty.

    :param api: Type of the LLM request, default value is chat.
    :type api: str
    :param configuration: Prompty model connection configuration
    :type configuration: Union[dict, AzureOpenAIModelConfiguration, OpenAIModelConfiguration]
    :param parameters: Params of the LLM request.
    :type parameters: dict
    :param response: Return the complete response or the first choice, default value is first.
    :type response: str
    """

    configuration: Union[dict, AzureOpenAIModelConfiguration, OpenAIModelConfiguration]
    parameters: dict
    api: str = "chat"
    response: str = "first"

    def __post_init__(self):
        if isinstance(self.configuration, dict):
            # Load connection from model configuration
            model_config = {
                k: v
                for k, v in self.configuration.items()
                if k not in ["type", "connection", "model", "azure_deployment"]
            }
            if self.configuration.get("connection", None) and any([v for v in model_config.values()]):
                raise InvalidConnectionError(
                    "Cannot configure model config and connection in configuration at the same time."
                )
            self._model = self.configuration.get("azure_deployment", None) or self.configuration.get("model", None)
        elif isinstance(self.configuration, OpenAIModelConfiguration):
            self._model = self.configuration.model
        elif isinstance(self.configuration, AzureOpenAIModelConfiguration):
            self._model = self.configuration.azure_deployment
