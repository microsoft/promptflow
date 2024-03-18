# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import importlib
import os
import types
from typing import Dict, List

from promptflow._constants import CONNECTION_SCRUBBED_VALUE as SCRUBBED_VALUE
from promptflow._constants import ConnectionAuthMode, ConnectionType, CustomStrongTypeConnectionConfigs
from promptflow._core.token_provider import AzureTokenProvider
from promptflow._utils.logger_utils import LoggerFactory
from promptflow._utils.utils import in_jupyter_notebook
from promptflow.contracts.types import Secret
from promptflow.core._errors import RequiredEnvironmentVariablesNotSetError
from promptflow.exceptions import UserErrorException

logger = LoggerFactory.get_logger(name=__name__)
PROMPTFLOW_CONNECTIONS = "promptflow.connections"


class _Connection:
    """A connection entity that stores the connection information.

    :param name: Connection name
    :type name: str
    :param type: Possible values include: "OpenAI", "AzureOpenAI", "Custom".
    :type type: str
    :param module: The module of connection class, used for execution.
    :type module: str
    :param configs: The configs kv pairs.
    :type configs: Dict[str, str]
    :param secrets: The secrets kv pairs.
    :type secrets: Dict[str, str]
    """

    TYPE = ConnectionType._NOT_SET.value

    def __init__(
        self,
        name: str = None,
        module: str = "promptflow.connections",
        configs: Dict[str, str] = None,
        secrets: Dict[str, str] = None,
        **kwargs,
    ):
        self.name = name
        self.type = self.TYPE
        self.class_name = f"{self.TYPE}Connection"  # The type in executor connection dict
        self.configs = configs or {}
        self.module = module
        # Note the connection secrets value behaviors:
        # --------------------------------------------------------------------------------
        # | secret value     | CLI create   | CLI update          | SDK create_or_update |
        # --------------------------------------------------------------------------------
        # | empty or all "*" | prompt input | use existing values | use existing values  |
        # | <no-change>      | prompt input | use existing values | use existing values  |
        # | <user-input>     | prompt input | prompt input        | raise error          |
        # --------------------------------------------------------------------------------
        self.secrets = secrets or {}
        self._secrets = {**self.secrets}  # Un-scrubbed secrets
        self.expiry_time = kwargs.get("expiry_time", None)
        self.created_date = kwargs.get("created_date", None)
        self.last_modified_date = kwargs.get("last_modified_date", None)
        # Conditional assignment to prevent entity bloat when unused.
        print_as_yaml = kwargs.pop("print_as_yaml", in_jupyter_notebook())
        if print_as_yaml:
            self.print_as_yaml = True

    def keys(self) -> List:
        """Return keys of the connection properties."""
        return list(self.configs.keys()) + list(self.secrets.keys())

    def __getitem__(self, item):
        # Note: This is added to allow usage **connection().
        if item in self.secrets:
            return self.secrets[item]
        if item in self.configs:
            return self.configs[item]
        # raise UserErrorException(error=KeyError(f"Key {item!r} not found in connection {self.name!r}."))
        # Cant't raise UserErrorException due to the code exit(1) of promptflow._cli._utils.py line 368.
        raise KeyError(f"Key {item!r} not found in connection {self.name!r}.")


class _StrongTypeConnection(_Connection):
    @property
    def _has_api_key(self):
        """Return if the connection has api key."""
        return True

    @property
    def api_key(self):
        """Return the api key."""
        return self.secrets.get("api_key", SCRUBBED_VALUE) if self._has_api_key else None

    @api_key.setter
    def api_key(self, value):
        """Set the api key."""
        self.secrets["api_key"] = value


class AzureOpenAIConnection(_StrongTypeConnection):
    """Azure Open AI connection.

    :param api_key: The api key.
    :type api_key: str
    :param api_base: The api base.
    :type api_base: str
    :param api_type: The api type, default "azure".
    :type api_type: str
    :param api_version: The api version, default "2023-07-01-preview".
    :type api_version: str
    :param auth_type: The auth type, supported value ["key", "meid_token"].
    :type api_version: str
    :param name: Connection name.
    :type name: str
    """

    TYPE = ConnectionType.AZURE_OPEN_AI.value

    def __init__(
        self,
        api_base: str,
        api_key: str = None,
        api_type: str = "azure",
        api_version: str = "2023-07-01-preview",
        auth_mode: str = ConnectionAuthMode.KEY,
        **kwargs,
    ):
        configs = {"api_base": api_base, "api_type": api_type, "api_version": api_version, "auth_mode": auth_mode}
        secrets = {"api_key": api_key} if auth_mode == ConnectionAuthMode.KEY else {}
        self._token_provider = kwargs.get("token_provider")
        super().__init__(configs=configs, secrets=secrets, **kwargs)

    @property
    def api_base(self):
        """Return the connection api base."""
        return self.configs.get("api_base")

    @api_base.setter
    def api_base(self, value):
        """Set the connection api base."""
        self.configs["api_base"] = value

    @property
    def api_type(self):
        """Return the connection api type."""
        return self.configs.get("api_type")

    @api_type.setter
    def api_type(self, value):
        """Set the connection api type."""
        self.configs["api_type"] = value

    @property
    def api_version(self):
        """Return the connection api version."""
        return self.configs.get("api_version")

    @api_version.setter
    def api_version(self, value):
        """Set the connection api version."""
        self.configs["api_version"] = value

    @property
    def auth_mode(self):
        """Return the connection auth mode."""
        return self.configs.get("auth_mode", ConnectionAuthMode.KEY)

    @auth_mode.setter
    def auth_mode(self, value):
        """Set the connection auth mode."""
        self.configs["auth_mode"] = value

    @property
    def _has_api_key(self):
        """Return if the connection has api key."""
        return self.auth_mode == ConnectionAuthMode.KEY

    def get_token(self):
        """Return the connection token."""
        if not self._token_provider:
            self._token_provider = AzureTokenProvider()

        return self._token_provider.get_token()

    @classmethod
    def from_env(cls, name=None):
        """
        Build connection from environment variables.

        Relevant environment variables:
        - AZURE_OPENAI_ENDPOINT: The api base.
        - AZURE_OPENAI_API_KEY: The api key.
        - OPENAI_API_VERSION: Optional. The api version, default "2023-07-01-preview".
        """
        # Env var name reference: https://github.com/openai/openai-python/blob/main/src/openai/lib/azure.py#L160
        api_base = os.getenv("AZURE_OPENAI_ENDPOINT")
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        # Note: Name OPENAI_API_VERSION from OpenAI.
        api_version = os.getenv("OPENAI_API_VERSION")
        if api_base is None or api_key is None:
            raise RequiredEnvironmentVariablesNotSetError(
                env_vars=["AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY"], cls_name=cls.__name__
            )
        # Note: Do not pass api_version None when init class object as we have default version.
        optional_args = {"api_version": api_version} if api_version else {}
        return cls(api_base=api_base, api_key=api_key, name=name, **optional_args)


class OpenAIConnection(_StrongTypeConnection):
    """Open AI connection.

    :param api_key: The api key.
    :type api_key: str
    :param organization: Optional. The unique identifier for your organization which can be used in API requests.
    :type organization: str
    :param base_url: Optional. Specify when use customized api base, leave None to use open ai default api base.
    :type base_url: str
    :param name: Connection name.
    :type name: str
    """

    TYPE = ConnectionType.OPEN_AI.value

    def __init__(self, api_key: str, organization: str = None, base_url=None, **kwargs):
        if base_url == "":
            # Keep empty as None to avoid disturbing openai pick the default api base.
            base_url = None
        configs = {"organization": organization, "base_url": base_url}
        secrets = {"api_key": api_key}
        super().__init__(configs=configs, secrets=secrets, **kwargs)

    @property
    def organization(self):
        """Return the connection organization."""
        return self.configs.get("organization")

    @organization.setter
    def organization(self, value):
        """Set the connection organization."""
        self.configs["organization"] = value

    @property
    def base_url(self):
        """Return the connection api base."""
        return self.configs.get("base_url")

    @base_url.setter
    def base_url(self, value):
        """Set the connection api base."""
        self.configs["base_url"] = value

    @classmethod
    def from_env(cls, name=None):
        """
        Build connection from environment variables.

        Relevant environment variables:
        - OPENAI_API_KEY: The api key.
        - OPENAI_ORG_ID: Optional. The unique identifier for your organization which can be used in API requests.
        - OPENAI_BASE_URL: Optional. Specify when use customized api base, leave None to use OpenAI default api base.
        """
        # Env var name reference: https://github.com/openai/openai-python/blob/main/src/openai/_client.py#L92
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        organization = os.getenv("OPENAI_ORG_ID")
        if api_key is None:
            raise RequiredEnvironmentVariablesNotSetError(env_vars=["OPENAI_API_KEY"], cls_name=cls.__name__)
        return cls(api_key=api_key, organization=organization, base_url=base_url, name=name)


class ServerlessConnection(_StrongTypeConnection):
    """Serverless connection.

    :param api_key: The api key.
    :type api_key: str
    :param api_base: The api base.
    :type api_base: str
    :param name: Connection name.
    :type name: str
    """

    TYPE = ConnectionType.SERVERLESS.value

    def __init__(self, api_key: str, api_base: str, **kwargs):
        secrets = {"api_key": api_key}
        configs = {"api_base": api_base}
        super().__init__(secrets=secrets, configs=configs, **kwargs)

    @property
    def api_base(self):
        """Return the connection api base."""
        return self.configs.get("api_base")

    @api_base.setter
    def api_base(self, value):
        """Set the connection api base."""
        self.configs["api_base"] = value


class SerpConnection(_StrongTypeConnection):
    """Serp connection.

    :param api_key: The api key.
    :type api_key: str
    :param name: Connection name.
    :type name: str
    """

    TYPE = ConnectionType.SERP.value

    def __init__(self, api_key: str, **kwargs):
        secrets = {"api_key": api_key}
        super().__init__(secrets=secrets, **kwargs)


class _EmbeddingStoreConnection(_StrongTypeConnection):
    TYPE = ConnectionType._NOT_SET.value

    def __init__(self, api_key: str, api_base: str, **kwargs):
        configs = {"api_base": api_base}
        secrets = {"api_key": api_key}
        super().__init__(module="promptflow_vectordb.connections", configs=configs, secrets=secrets, **kwargs)

    @property
    def api_base(self):
        return self.configs.get("api_base")

    @api_base.setter
    def api_base(self, value):
        self.configs["api_base"] = value


class QdrantConnection(_EmbeddingStoreConnection):
    """Qdrant connection.

    :param api_key: The api key.
    :type api_key: str
    :param api_base: The api base.
    :type api_base: str
    :param name: Connection name.
    :type name: str
    """

    TYPE = ConnectionType.QDRANT.value


class WeaviateConnection(_EmbeddingStoreConnection):
    """Weaviate connection.

    :param api_key: The api key.
    :type api_key: str
    :param api_base: The api base.
    :type api_base: str
    :param name: Connection name.
    :type name: str
    """

    TYPE = ConnectionType.WEAVIATE.value


class CognitiveSearchConnection(_StrongTypeConnection):
    """Cognitive Search connection.

    :param api_key: The api key.
    :type api_key: str
    :param api_base: The api base.
    :type api_base: str
    :param api_version: The api version, default "2023-07-01-Preview".
    :type api_version: str
    :param name: Connection name.
    :type name: str
    """

    TYPE = ConnectionType.COGNITIVE_SEARCH.value

    def __init__(self, api_key: str, api_base: str, api_version: str = "2023-07-01-Preview", **kwargs):
        configs = {"api_base": api_base, "api_version": api_version}
        secrets = {"api_key": api_key}
        super().__init__(configs=configs, secrets=secrets, **kwargs)

    @property
    def api_base(self):
        """Return the connection api base."""
        return self.configs.get("api_base")

    @api_base.setter
    def api_base(self, value):
        """Set the connection api base."""
        self.configs["api_base"] = value

    @property
    def api_version(self):
        """Return the connection api version."""
        return self.configs.get("api_version")

    @api_version.setter
    def api_version(self, value):
        """Set the connection api version."""
        self.configs["api_version"] = value


class AzureContentSafetyConnection(_StrongTypeConnection):
    """Azure Content Safety connection.

    :param api_key: The api key.
    :type api_key: str
    :param endpoint: The api endpoint.
    :type endpoint: str
    :param api_version: The api version, default "2023-04-30-preview".
    :type api_version: str
    :param api_type: The api type, default "Content Safety".
    :type api_type: str
    :param name: Connection name.
    :type name: str
    """

    TYPE = ConnectionType.AZURE_CONTENT_SAFETY.value

    def __init__(
        self,
        api_key: str,
        endpoint: str,
        api_version: str = "2023-10-01",
        api_type: str = "Content Safety",
        **kwargs,
    ):
        configs = {"endpoint": endpoint, "api_version": api_version, "api_type": api_type}
        secrets = {"api_key": api_key}
        super().__init__(configs=configs, secrets=secrets, **kwargs)

    @property
    def endpoint(self):
        """Return the connection endpoint."""
        return self.configs.get("endpoint")

    @endpoint.setter
    def endpoint(self, value):
        """Set the connection endpoint."""
        self.configs["endpoint"] = value

    @property
    def api_version(self):
        """Return the connection api version."""
        return self.configs.get("api_version")

    @api_version.setter
    def api_version(self, value):
        """Set the connection api version."""
        self.configs["api_version"] = value

    @property
    def api_type(self):
        """Return the connection api type."""
        return self.configs.get("api_type")

    @api_type.setter
    def api_type(self, value):
        """Set the connection api type."""
        self.configs["api_type"] = value


class FormRecognizerConnection(AzureContentSafetyConnection):
    """Form Recognizer connection.

    :param api_key: The api key.
    :type api_key: str
    :param endpoint: The api endpoint.
    :type endpoint: str
    :param api_version: The api version, default "2023-07-31".
    :type api_version: str
    :param api_type: The api type, default "Form Recognizer".
    :type api_type: str
    :param name: Connection name.
    :type name: str
    """

    # Note: FormRecognizer and ContentSafety are using CognitiveService type in ARM, so keys are the same.
    TYPE = ConnectionType.FORM_RECOGNIZER.value

    def __init__(
        self, api_key: str, endpoint: str, api_version: str = "2023-07-31", api_type: str = "Form Recognizer", **kwargs
    ):
        super().__init__(api_key=api_key, endpoint=endpoint, api_version=api_version, api_type=api_type, **kwargs)


class CustomStrongTypeConnection(_Connection):
    """Custom strong type connection.

    .. note::

        This connection type should not be used directly. Below is an example of how to use CustomStrongTypeConnection:

        .. code-block:: python

            class MyCustomConnection(CustomStrongTypeConnection):
                api_key: Secret
                api_base: str

    :param configs: The configs kv pairs.
    :type configs: Dict[str, str]
    :param secrets: The secrets kv pairs.
    :type secrets: Dict[str, str]
    :param name: Connection name
    :type name: str
    """

    def __init__(
        self,
        secrets: Dict[str, str],
        configs: Dict[str, str] = None,
        **kwargs,
    ):
        # There are two cases to init a Custom strong type connection:
        # 1. The connection is created through SDK PFClient, custom_type and custom_module are not in the kwargs.
        # 2. The connection is loaded from template file, custom_type and custom_module are in the kwargs.
        custom_type = kwargs.get(CustomStrongTypeConnectionConfigs.TYPE, None)
        custom_module = kwargs.get(CustomStrongTypeConnectionConfigs.MODULE, None)
        if custom_type:
            configs.update({CustomStrongTypeConnectionConfigs.PROMPTFLOW_TYPE_KEY: custom_type})
        if custom_module:
            configs.update({CustomStrongTypeConnectionConfigs.PROMPTFLOW_MODULE_KEY: custom_module})
        self.kwargs = kwargs
        super().__init__(configs=configs, secrets=secrets, **kwargs)
        self.module = kwargs.get("module", self.__class__.__module__)
        self.custom_type = custom_type or self.__class__.__name__
        self.package = kwargs.get(CustomStrongTypeConnectionConfigs.PACKAGE, None)
        self.package_version = kwargs.get(CustomStrongTypeConnectionConfigs.PACKAGE_VERSION, None)

    def __getattribute__(self, item):
        # Note: The reason to overwrite __getattribute__ instead of __getattr__ is as follows:
        # Custom strong type connection is written this way:
        # class MyCustomConnection(CustomStrongTypeConnection):
        #     api_key: Secret
        #     api_base: str = "This is a default value"
        # api_base has a default value, my_custom_connection_instance.api_base would not trigger __getattr__.
        # The default value will be returned directly instead of the real value in configs.
        annotations = getattr(super().__getattribute__("__class__"), "__annotations__", {})
        if item in annotations:
            if annotations[item] == Secret:
                return self.secrets[item]
            else:
                return self.configs[item]
        return super().__getattribute__(item)

    def __setattr__(self, key, value):
        annotations = getattr(super().__getattribute__("__class__"), "__annotations__", {})
        if key in annotations:
            if annotations[key] == Secret:
                self.secrets[key] = value
            else:
                self.configs[key] = value
        return super().__setattr__(key, value)

    def _convert_to_custom(self):
        # update configs
        self.configs.update({CustomStrongTypeConnectionConfigs.PROMPTFLOW_TYPE_KEY: self.custom_type})
        self.configs.update({CustomStrongTypeConnectionConfigs.PROMPTFLOW_MODULE_KEY: self.module})
        if self.package and self.package_version:
            self.configs.update({CustomStrongTypeConnectionConfigs.PROMPTFLOW_PACKAGE_KEY: self.package})
            self.configs.update(
                {CustomStrongTypeConnectionConfigs.PROMPTFLOW_PACKAGE_VERSION_KEY: self.package_version}
            )

        custom_connection = CustomConnection(configs=self.configs, secrets=self.secrets, **self.kwargs)
        return custom_connection

    @classmethod
    def _get_custom_keys(cls, data: Dict):
        # The data could be either from yaml or from DB.
        # If from yaml, 'custom_type' and 'module' are outside the configs of data.
        # If from DB, 'custom_type' and 'module' are within the configs of data.
        if not data.get(CustomStrongTypeConnectionConfigs.TYPE) or not data.get(
            CustomStrongTypeConnectionConfigs.MODULE
        ):
            if (
                not data["configs"][CustomStrongTypeConnectionConfigs.PROMPTFLOW_TYPE_KEY]
                or not data["configs"][CustomStrongTypeConnectionConfigs.PROMPTFLOW_MODULE_KEY]
            ):
                error = ValueError("custom_type and module are required for custom strong type connections.")
                raise UserErrorException(message=str(error), error=error)
            else:
                m = data["configs"][CustomStrongTypeConnectionConfigs.PROMPTFLOW_MODULE_KEY]
                custom_cls = data["configs"][CustomStrongTypeConnectionConfigs.PROMPTFLOW_TYPE_KEY]
        else:
            m = data[CustomStrongTypeConnectionConfigs.MODULE]
            custom_cls = data[CustomStrongTypeConnectionConfigs.TYPE]

        try:
            module = importlib.import_module(m)
            cls = getattr(module, custom_cls)
        except ImportError:
            error = ValueError(
                f"Can't find module {m} in current environment. Please check the module is correctly configured."
            )
            raise UserErrorException(message=str(error), error=error)
        except AttributeError:
            error = ValueError(
                f"Can't find class {custom_cls} in module {m}. "
                f"Please check the custom_type is correctly configured."
            )
            raise UserErrorException(message=str(error), error=error)

        schema_configs = {}
        schema_secrets = {}

        for k, v in cls.__annotations__.items():
            if v == Secret:
                schema_secrets[k] = v
            else:
                schema_configs[k] = v

        return schema_configs, schema_secrets


class CustomConnection(_Connection):
    """Custom connection.

    :param configs: The configs kv pairs.
    :type configs: Dict[str, str]
    :param secrets: The secrets kv pairs.
    :type secrets: Dict[str, str]
    :param name: Connection name
    :type name: str
    """

    TYPE = ConnectionType.CUSTOM.value

    def __init__(
        self,
        secrets: Dict[str, str],
        configs: Dict[str, str] = None,
        **kwargs,
    ):
        super().__init__(secrets=secrets, configs=configs, **kwargs)

    def __getattr__(self, item):
        # Note: This is added for compatibility with promptflow.connections custom connection usage.
        if item == "secrets":
            # Usually obj.secrets will not reach here
            # This is added to handle copy.deepcopy loop issue
            return super().__getattribute__("secrets")
        if item == "configs":
            # Usually obj.configs will not reach here
            # This is added to handle copy.deepcopy loop issue
            return super().__getattribute__("configs")
        if item in self.secrets:
            logger.warning("Please use connection.secrets[key] to access secrets.")
            return self.secrets[item]
        if item in self.configs:
            logger.warning("Please use connection.configs[key] to access configs.")
            return self.configs[item]
        return super().__getattribute__(item)

    def is_secret(self, item):
        """Check if item is a secret."""
        # Note: This is added for compatibility with promptflow.connections custom connection usage.
        return item in self.secrets

    def _is_custom_strong_type(self):
        return (
            CustomStrongTypeConnectionConfigs.PROMPTFLOW_TYPE_KEY in self.configs
            and self.configs[CustomStrongTypeConnectionConfigs.PROMPTFLOW_TYPE_KEY]
        )

    def _convert_to_custom_strong_type(self, module=None, to_class=None) -> CustomStrongTypeConnection:
        # There are two scenarios to convert a custom connection to custom strong type connection:
        # 1. The connection is created from a custom strong type connection template file.
        #    Custom type and module name are present in the configs.
        # 2. The connection is created through SDK PFClient or a custom connection template file.
        #    Custom type and module name are not present in the configs. Module and class must be passed for conversion.
        if to_class == self.__class__.__name__:
            # No need to convert.
            return self

        import importlib

        if (
            CustomStrongTypeConnectionConfigs.PROMPTFLOW_MODULE_KEY in self.configs
            and CustomStrongTypeConnectionConfigs.PROMPTFLOW_TYPE_KEY in self.configs
        ):
            module_name = self.configs.get(CustomStrongTypeConnectionConfigs.PROMPTFLOW_MODULE_KEY)
            module = importlib.import_module(module_name)
            custom_conn_name = self.configs.get(CustomStrongTypeConnectionConfigs.PROMPTFLOW_TYPE_KEY)
        elif isinstance(module, str) and isinstance(to_class, str):
            module_name = module
            module = importlib.import_module(module_name)
            custom_conn_name = to_class
        elif isinstance(module, types.ModuleType) and isinstance(to_class, str):
            custom_conn_name = to_class
        else:
            error = ValueError(
                f"Failed to convert to custom strong type connection because of "
                f"invalid module or class: {module}, {to_class}"
            )
            raise UserErrorException(message=str(error), error=error)

        custom_defined_connection_class = getattr(module, custom_conn_name)

        connection_instance = custom_defined_connection_class(configs=self.configs, secrets=self.secrets)

        return connection_instance
