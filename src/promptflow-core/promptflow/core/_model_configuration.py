import abc
from dataclasses import dataclass
from typing import Union

from promptflow._constants import ConnectionType
from promptflow.core._connection import AzureOpenAIConnection, OpenAIConnection
from promptflow.core._errors import InvalidConnectionError


class ModelConfiguration:
    @classmethod
    @abc.abstractmethod
    def from_connection(cls, connection, **kwargs):
        """Create a model configuration from a connection."""
        pass


@dataclass
class AzureOpenAIModelConfiguration(ModelConfiguration):
    azure_deployment: str
    azure_endpoint: str = None
    api_version: str = None
    api_key: str = None
    # connection and model configs are exclusive.
    connection: str = None

    def __post_init__(self):
        self._type = ConnectionType.AZURE_OPEN_AI
        if any([self.azure_endpoint, self.api_key, self.api_version]) and self.connection:
            raise InvalidConnectionError("Cannot configure model config and connection at the same time.")

    @classmethod
    def from_connection(cls, connection: AzureOpenAIConnection, azure_deployment: str):
        """Create a model configuration from an Azure OpenAI connection.

        :param connection: AzureOpenAI Connection object.
        :type connection: promptflow.connections.AzureOpenAIConnection
        :param azure_deployment: Azure deployment name.
        :type azure_deployment: str
        """
        return cls(
            azure_deployment=azure_deployment,
            azure_endpoint=connection.api_base,
            api_version=connection.api_version,
            api_key=connection.api_key,
        )


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
        if any([self.base_url, self.api_key, self.organization]) and self.connection:
            raise InvalidConnectionError("Cannot configure model config and connection at the same time.")

    @classmethod
    def from_connection(cls, connection: OpenAIConnection, model: str):
        """Create a model configuration from an OpenAI connection.

        :param connection: OpenAI Connection object.
        :type connection: promptflow.connections.OpenAIConnection
        :param model: model name.
        :type model: str
        """
        return cls(
            model=model,
            base_url=connection.base_url,
            api_key=connection.api_key,
            organization=connection.organization,
        )


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


MODEL_CONFIG_NAME_2_CLASS = {
    AzureOpenAIModelConfiguration.__name__: AzureOpenAIModelConfiguration,
    OpenAIModelConfiguration.__name__: OpenAIModelConfiguration,
}
