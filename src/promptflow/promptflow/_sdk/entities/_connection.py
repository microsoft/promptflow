# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import abc
import copy
import json
from os import PathLike
from pathlib import Path
from typing import Dict, List, Union

from promptflow._sdk._constants import (
    BASE_PATH_CONTEXT_KEY,
    PARAMS_OVERRIDE_KEY,
    SCRUBBED_VALUE,
    SCRUBBED_VALUE_NO_CHANGE,
    SCRUBBED_VALUE_USER_INPUT,
    ConfigValueType,
    ConnectionType,
    CustomStrongTypeConnectionConfigs,
)
from promptflow._sdk._errors import UnsecureConnectionError
from promptflow._sdk._logger_factory import LoggerFactory
from promptflow._sdk._orm.connection import Connection as ORMConnection
from promptflow._sdk._utils import (
    decrypt_secret_value,
    encrypt_secret_value,
    find_type_in_override,
    in_jupyter_notebook,
    print_yellow_warning,
    snake_to_camel,
)
from promptflow._sdk.entities._yaml_translatable import YAMLTranslatableMixin
from promptflow._sdk.schemas._connection import (
    AzureContentSafetyConnectionSchema,
    AzureOpenAIConnectionSchema,
    CognitiveSearchConnectionSchema,
    CustomConnectionSchema,
    CustomStrongTypeConnectionSchema,
    FormRecognizerConnectionSchema,
    OpenAIConnectionSchema,
    QdrantConnectionSchema,
    SerpConnectionSchema,
    WeaviateConnectionSchema,
)
from promptflow.contracts.types import Secret

logger = LoggerFactory.get_logger(name=__name__)
PROMPTFLOW_CONNECTIONS = "promptflow.connections"


class _Connection(YAMLTranslatableMixin):
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

    TYPE = ConnectionType._NOT_SET

    def __init__(
        self,
        name: str = "default_connection",
        module: str = "promptflow.connections",
        configs: Dict[str, str] = None,
        secrets: Dict[str, str] = None,
        **kwargs,
    ):
        self.name = name
        self.type = self.TYPE
        self.class_name = f"{self.TYPE.value}Connection"  # The type in executor connection dict
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

    @classmethod
    def _casting_type(cls, typ):
        type_dict = {
            "azure_open_ai": ConnectionType.AZURE_OPEN_AI.value,
            "open_ai": ConnectionType.OPEN_AI.value,
        }

        if typ in type_dict:
            return type_dict.get(typ)
        return snake_to_camel(typ)

    def keys(self) -> List:
        """Return keys of the connection properties."""
        return list(self.configs.keys()) + list(self.secrets.keys())

    def __getitem__(self, item):
        # Note: This is added to allow usage **connection().
        if item in self.secrets:
            return self.secrets[item]
        if item in self.configs:
            return self.configs[item]
        raise KeyError(f"Key {item!r} not found in connection {self.name!r}.")

    @classmethod
    def _is_scrubbed_value(cls, value):
        """For scrubbed value, cli will get original for update, and prompt user to input for create."""
        if value is None or not value:
            return True
        if all([v == "*" for v in value]):
            return True
        return value == SCRUBBED_VALUE_NO_CHANGE

    @classmethod
    def _is_user_input_value(cls, value):
        """The value will prompt user to input in cli for both create and update."""
        return value == SCRUBBED_VALUE_USER_INPUT

    def _validate_and_encrypt_secrets(self):
        encrypt_secrets = {}
        invalid_secrets = []
        for k, v in self.secrets.items():
            # In sdk experience, if v is not scrubbed, use it.
            # If v is scrubbed, try to use the value in _secrets.
            # If v is <user-input>, raise error.
            if self._is_scrubbed_value(v):
                # Try to get the value not scrubbed.
                v = self._secrets.get(k)
            if self._is_scrubbed_value(v) or self._is_user_input_value(v):
                # Can't find the original value or is <user-input>, raise error.
                invalid_secrets.append(k)
                continue
            encrypt_secrets[k] = encrypt_secret_value(v)
        if invalid_secrets:
            raise ValueError(f"Connection {self.name!r} secrets {invalid_secrets} value invalid, please fill them.")
        return encrypt_secrets

    @classmethod
    def _load_from_dict(cls, data: Dict, context: Dict, additional_message: str = None, **kwargs):
        schema_cls = cls._get_schema_cls()
        try:
            loaded_data = schema_cls(context=context).load(data, **kwargs)
        except Exception as e:
            raise Exception(f"Load connection failed with {str(e)}. f{(additional_message or '')}.")
        return cls(base_path=context[BASE_PATH_CONTEXT_KEY], **loaded_data)

    def _to_dict(self) -> Dict:
        schema_cls = self._get_schema_cls()
        return schema_cls(context={BASE_PATH_CONTEXT_KEY: "./"}).dump(self)

    @classmethod
    # pylint: disable=unused-argument
    def _resolve_cls_and_type(cls, data, params_override=None):
        type_in_override = find_type_in_override(params_override)
        type_str = type_in_override or data.get("type")
        if type_str is None:
            raise ValueError("type is required for connection.")
        type_str = cls._casting_type(type_str)
        type_cls = _supported_types.get(type_str)
        if type_cls is None:
            # Should check for custom strong type connection. When update, the custom_type should match
            # if not should throw an error msg like this indication current custom type and supported one.
            raise ValueError(
                f"connection_type {type_str!r} is not supported. Supported types are: {list(_supported_types.keys())}"
            )
        return type_cls, type_str

    @abc.abstractmethod
    def _to_orm_object(self) -> ORMConnection:
        pass

    @classmethod
    def _from_mt_rest_object(cls, mt_rest_obj) -> "_Connection":
        type_cls, _ = cls._resolve_cls_and_type(data={"type": mt_rest_obj.connection_type})
        obj = type_cls._from_mt_rest_object(mt_rest_obj)
        return obj

    @classmethod
    def _from_orm_object_with_secrets(cls, orm_object: ORMConnection):
        # !!! Attention !!!: Do not use this function to user facing api, use _from_orm_object to remove secrets.
        type_cls, _ = cls._resolve_cls_and_type(data={"type": orm_object.connectionType})
        obj = type_cls._from_orm_object_with_secrets(orm_object)
        return obj

    @classmethod
    def _from_orm_object(cls, orm_object: ORMConnection):
        """This function will create a connection object then scrub secrets."""
        type_cls, _ = cls._resolve_cls_and_type(data={"type": orm_object.connectionType})
        obj = type_cls._from_orm_object_with_secrets(orm_object)
        # Note: we may can't get secret keys for custom connection from MT
        obj.secrets = {k: SCRUBBED_VALUE for k in obj.secrets}
        return obj

    @classmethod
    def _load(
        cls,
        data: Dict = None,
        yaml_path: Union[PathLike, str] = None,
        params_override: list = None,
        connection_spec=None,
        **kwargs,
    ) -> "_Connection":
        """Load a job object from a yaml file.

        :param cls: Indicates that this is a class method.
        :type cls: class
        :param data: Data Dictionary, defaults to None
        :type data: Dict, optional
        :param yaml_path: YAML Path, defaults to None
        :type yaml_path: Union[PathLike, str], optional
        :param params_override: Fields to overwrite on top of the yaml file.
            Format is [{"field1": "value1"}, {"field2": "value2"}], defaults to None
        :type params_override: List[Dict], optional
        :param kwargs: A dictionary of additional configuration parameters.
        :type kwargs: dict
        :raises Exception: An exception
        :return: Loaded job object.
        :rtype: Job
        """
        data = data or {}
        params_override = params_override or []
        context = {
            BASE_PATH_CONTEXT_KEY: Path(yaml_path).parent if yaml_path else Path("../../azure/_entities/"),
            PARAMS_OVERRIDE_KEY: params_override,
        }
        if connection_spec:
            context["connection_spec"] = connection_spec
        connection_type, type_str = cls._resolve_cls_and_type(data, params_override)
        connection = connection_type._load_from_dict(
            data=data,
            context=context,
            additional_message=f"If you are trying to configure a job that is not of type {type_str}, please specify "
            f"the correct connection type in the 'type' property.",
            **kwargs,
        )
        return connection

    def _to_execution_connection_dict(self) -> dict:
        value = {**self.configs, **self.secrets}
        secret_keys = list(self.secrets.keys())
        return {
            "type": self.class_name,  # Required class name for connection in executor
            "module": self.module,
            "value": value,
            "secret_keys": secret_keys,
        }

    @classmethod
    def _from_execution_connection_dict(cls, name, data) -> "_Connection":
        type_cls, _ = cls._resolve_cls_and_type(data={"type": data.get("type")[: -len("Connection")]})
        value_dict = data.get("value", {})
        if type_cls == CustomConnection:
            secrets = {k: v for k, v in value_dict.items() if k in data.get("secret_keys", [])}
            configs = {k: v for k, v in value_dict.items() if k not in secrets}
            return CustomConnection(name=name, configs=configs, secrets=secrets)
        return type_cls(name=name, **value_dict)

    def is_type_not_set(self):
        return self.TYPE == ConnectionType._NOT_SET


class _StrongTypeConnection(_Connection):
    def _to_orm_object(self):
        # Both keys & secrets will be stored in configs for strong type connection.
        secrets = self._validate_and_encrypt_secrets()
        return ORMConnection(
            connectionName=self.name,
            connectionType=self.type.value,
            configs=json.dumps({**self.configs, **secrets}),
            customConfigs="{}",
            expiryTime=self.expiry_time,
            createdDate=self.created_date,
            lastModifiedDate=self.last_modified_date,
        )

    @classmethod
    def _from_orm_object_with_secrets(cls, orm_object: ORMConnection):
        # !!! Attention !!!: Do not use this function to user facing api, use _from_orm_object to remove secrets.
        # Both keys & secrets will be stored in configs for strong type connection.
        type_cls, _ = cls._resolve_cls_and_type(data={"type": orm_object.connectionType})
        obj = type_cls(
            name=orm_object.connectionName,
            expiry_time=orm_object.expiryTime,
            created_date=orm_object.createdDate,
            last_modified_date=orm_object.lastModifiedDate,
            **json.loads(orm_object.configs),
        )
        obj.secrets = {k: decrypt_secret_value(obj.name, v) for k, v in obj.secrets.items()}
        obj._secrets = {**obj.secrets}
        return obj

    @classmethod
    def _from_mt_rest_object(cls, mt_rest_obj):
        type_cls, _ = cls._resolve_cls_and_type(data={"type": mt_rest_obj.connection_type})
        obj = type_cls(
            name=mt_rest_obj.connection_name,
            expiry_time=mt_rest_obj.expiry_time,
            created_date=mt_rest_obj.created_date,
            last_modified_date=mt_rest_obj.last_modified_date,
            **mt_rest_obj.configs,
        )
        return obj

    @property
    def api_key(self):
        """Return the api key."""
        return self.secrets.get("api_key", SCRUBBED_VALUE)

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
    :param name: Connection name.
    :type name: str
    """

    TYPE = ConnectionType.AZURE_OPEN_AI

    def __init__(
        self, api_key: str, api_base: str, api_type: str = "azure", api_version: str = "2023-07-01-preview", **kwargs
    ):
        configs = {"api_base": api_base, "api_type": api_type, "api_version": api_version}
        secrets = {"api_key": api_key}
        super().__init__(configs=configs, secrets=secrets, **kwargs)

    @classmethod
    def _get_schema_cls(cls):
        return AzureOpenAIConnectionSchema

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


class OpenAIConnection(_StrongTypeConnection):
    """Open AI connection.

    :param api_key: The api key.
    :type api_key: str
    :param organization: Optional. The unique identifier for your organization which can be used in API requests.
    :type organization: str
    :param name: Connection name.
    :type name: str
    """

    TYPE = ConnectionType.OPEN_AI

    def __init__(self, api_key: str, organization: str = None, **kwargs):
        configs = {"organization": organization}
        secrets = {"api_key": api_key}
        super().__init__(configs=configs, secrets=secrets, **kwargs)

    @classmethod
    def _get_schema_cls(cls):
        return OpenAIConnectionSchema

    @property
    def organization(self):
        """Return the connection organization."""
        return self.configs.get("organization")

    @organization.setter
    def organization(self, value):
        """Set the connection organization."""
        self.configs["organization"] = value


class SerpConnection(_StrongTypeConnection):
    """Serp connection.

    :param api_key: The api key.
    :type api_key: str
    :param name: Connection name.
    :type name: str
    """

    TYPE = ConnectionType.SERP

    def __init__(self, api_key: str, **kwargs):
        secrets = {"api_key": api_key}
        super().__init__(secrets=secrets, **kwargs)

    @classmethod
    def _get_schema_cls(cls):
        return SerpConnectionSchema


class _EmbeddingStoreConnection(_StrongTypeConnection):
    TYPE = ConnectionType._NOT_SET

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

    TYPE = ConnectionType.QDRANT

    @classmethod
    def _get_schema_cls(cls):
        return QdrantConnectionSchema


class WeaviateConnection(_EmbeddingStoreConnection):
    """Weaviate connection.

    :param api_key: The api key.
    :type api_key: str
    :param api_base: The api base.
    :type api_base: str
    :param name: Connection name.
    :type name: str
    """

    TYPE = ConnectionType.WEAVIATE

    @classmethod
    def _get_schema_cls(cls):
        return WeaviateConnectionSchema


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

    TYPE = ConnectionType.COGNITIVE_SEARCH

    def __init__(self, api_key: str, api_base: str, api_version: str = "2023-07-01-Preview", **kwargs):
        configs = {"api_base": api_base, "api_version": api_version}
        secrets = {"api_key": api_key}
        super().__init__(configs=configs, secrets=secrets, **kwargs)

    @classmethod
    def _get_schema_cls(cls):
        return CognitiveSearchConnectionSchema

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

    TYPE = ConnectionType.AZURE_CONTENT_SAFETY

    def __init__(
        self,
        api_key: str,
        endpoint: str,
        api_version: str = "2023-04-30-preview",
        api_type: str = "Content Safety",
        **kwargs,
    ):
        configs = {"endpoint": endpoint, "api_version": api_version, "api_type": api_type}
        secrets = {"api_key": api_key}
        super().__init__(configs=configs, secrets=secrets, **kwargs)

    @classmethod
    def _get_schema_cls(cls):
        return AzureContentSafetyConnectionSchema

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
    TYPE = ConnectionType.FORM_RECOGNIZER

    def __init__(
        self, api_key: str, endpoint: str, api_version: str = "2023-07-31", api_type: str = "Form Recognizer", **kwargs
    ):
        super().__init__(api_key=api_key, endpoint=endpoint, api_version=api_version, api_type=api_type, **kwargs)

    @classmethod
    def _get_schema_cls(cls):
        return FormRecognizerConnectionSchema


class CustomStrongTypeConnection(_Connection):
    def __init__(self, **kwargs):
        configs = {}
        secrets = {}
        for k, v in self.__class__.__annotations__.items():
            field_value = kwargs.get(k, None)
            if v == Secret:
                secrets[k] = field_value
            else:
                configs[k] = field_value
        if not secrets:
            raise ValueError(f"Secrets is required for {_Connection.__class__.__name__}.")
        module = self.__class__.__module__
        super().__init__(secrets=secrets, configs=configs, module=module, **kwargs)

    def __setattr__(self, key, value):
        if key in self.__annotations__:
            if isinstance(value, Secret):
                self.secrets[key] = value
            else:
                self.configs[key] = value
        else:
            super().__setattr__(key, value)

    def is_custom_strong_type(self):
        return True

    def _from_orm_object_with_secrets(cls, orm_object: ORMConnection):
        pass

    def _to_orm_object(self) -> ORMConnection:
        pass


class CustomConnection(_Connection):
    """Custom connection.

    :param configs: The configs kv pairs.
    :type configs: Dict[str, str]
    :param secrets: The secrets kv pairs.
    :type secrets: Dict[str, str]
    :param name: Connection name
    :type name: str
    :is_custom_strong_type: Whether the custom connection is strong type.
    """

    TYPE = ConnectionType.CUSTOM

<<<<<<< HEAD
    def __init__(self, secrets: Dict[str, str], configs: Dict[str, str] = None, is_azureml_custom_strong_type_connection = False, **kwargs):
=======
    def __init__(
        self,
        secrets: Dict[str, str],
        configs: Dict[str, str] = None,
        is_azureml_custom_strong_type_connection=False,
        **kwargs,
    ):
        if not secrets:
            raise ValueError(
                "Secrets is required for custom connection, "
                "please use CustomConnection(configs={key1: val1}, secrets={key2: val2}) "
                "to initialize custom connection."
            )
>>>>>>> 615f94eb (fix flake8 and add tests)
        # When create connection through file, we can't check if it is custom strong type through self.custom_type
        # So we need a hint 'is_custom_strong_type' to indicate it.
        if is_azureml_custom_strong_type_connection:
            configs.update(
                {CustomStrongTypeConnectionConfigs.FULL_TYPE: kwargs.get(CustomStrongTypeConnectionConfigs.TYPE, None)}
            )
            configs.update(
                {
                    CustomStrongTypeConnectionConfigs.FULL_MODULE: kwargs.get(
                        CustomStrongTypeConnectionConfigs.MODULE, None
                    )
                }
            )
        super().__init__(secrets=secrets, configs=configs, **kwargs)
        self.custom_type = kwargs.get(CustomStrongTypeConnectionConfigs.TYPE, None)

    @classmethod
    def _get_schema_cls(cls, is_custom_strong_type=False):
        if is_custom_strong_type:
            return CustomStrongTypeConnectionSchema
        return CustomConnectionSchema

    @classmethod
    def _load_from_dict(cls, data: Dict, context: Dict, additional_message: str = None, **kwargs):
        # Note here are two cases:
        # 1. When create/load connection data from yaml, the custom_type and module are outside the configs of data.
        # 2. When update/load connection data from DB, the custom_type and module are within the configs of data.
        is_custom_strong_type = data.get(CustomStrongTypeConnectionConfigs.TYPE) or (
            data.get("configs") and data.get("configs").get(CustomStrongTypeConnectionConfigs.FULL_TYPE)
        )
        schema_cls = cls._get_schema_cls(is_custom_strong_type=is_custom_strong_type)
        try:
            loaded_data = schema_cls(context=context).load(data, **kwargs)
        except Exception as e:
            raise Exception(f"Load connection failed with {str(e)}. f{(additional_message or '')}.")
        return cls(
            base_path=context[BASE_PATH_CONTEXT_KEY],
            is_azureml_custom_strong_type_connection=is_custom_strong_type,
            **loaded_data,
        )

    def __setattr__(self, key, value):
        if hasattr(self, "custom_type") and self.is_custom_strong_type():
            if isinstance(value, Secret) and hasattr(self, "secrets") and key in self.secrets:
                self.secrets[key] = value
                return
            if not isinstance(value, Secret) and hasattr(self, "configs") and key in self.configs:
                self.configs[key] = value
                return
        super().__setattr__(key, value)

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
        if hasattr(self, "secrets") and item in self.secrets:
            logger.warning("Please use connection.secrets[key] to access secrets.")
            return self.secrets[item]
        if hasattr(self, "configs") and item in self.configs:
            logger.warning("Please use connection.configs[key] to access configs.")
            return self.configs[item]
        return super().__getattribute__(item)

    def is_secret(self, item):
        """Check if item is a secret."""
        # Note: This is added for compatibility with promptflow.connections custom connection usage.
        return item in self.secrets

    def _to_orm_object(self):
        # Both keys & secrets will be set in custom configs with value type specified for custom connection.
        if not self.secrets:
            raise ValueError(
                "Secrets is required for custom connection, "
                "please use CustomConnection(configs={key1: val1}, secrets={key2: val2}) "
                "to initialize custom connection."
            )
        custom_configs = {
            k: {"configValueType": ConfigValueType.STRING.value, "value": v} for k, v in self.configs.items()
        }
        encrypted_secrets = self._validate_and_encrypt_secrets()
        custom_configs.update(
            {k: {"configValueType": ConfigValueType.SECRET.value, "value": v} for k, v in encrypted_secrets.items()}
        )

        return ORMConnection(
            connectionName=self.name,
            connectionType=self.type.value,
            configs="{}",
            customConfigs=json.dumps(custom_configs),
            expiryTime=self.expiry_time,
            createdDate=self.created_date,
            lastModifiedDate=self.last_modified_date,
        )

    @classmethod
    def _from_orm_object_with_secrets(cls, orm_object: ORMConnection):
        # !!! Attention !!!: Do not use this function to user facing api, use _from_orm_object to remove secrets.
        # Both keys & secrets will be set in custom configs with value type specified for custom connection.
        configs = {
            k: v["value"]
            for k, v in json.loads(orm_object.customConfigs).items()
            if v["configValueType"] == ConfigValueType.STRING.value
        }

        secrets = {}
        unsecure_connection = False
        custom_type = None
        for k, v in json.loads(orm_object.customConfigs).items():
            if k == CustomStrongTypeConnectionConfigs.FULL_TYPE:
                custom_type = v["value"]
                continue
            if not v["configValueType"] == ConfigValueType.SECRET.value:
                continue
            try:
                secrets[k] = decrypt_secret_value(orm_object.connectionName, v["value"])
            except UnsecureConnectionError:
                # This is to workaround old custom secrets that are not encrypted with Fernet.
                unsecure_connection = True
                secrets[k] = v["value"]
        if unsecure_connection:
            print_yellow_warning(
                f"Warning: Please delete and re-create connection {orm_object.connectionName} "
                "due to a security issue in the old sdk version."
            )

        return cls(
            name=orm_object.connectionName,
            configs=configs,
            secrets=secrets,
            custom_type=custom_type,
            expiry_time=orm_object.expiryTime,
            created_date=orm_object.createdDate,
            last_modified_date=orm_object.lastModifiedDate,
        )

    @classmethod
    def _from_mt_rest_object(cls, mt_rest_obj):
        type_cls, _ = cls._resolve_cls_and_type(data={"type": mt_rest_obj.connection_type})
        if not mt_rest_obj.custom_configs:
            mt_rest_obj.custom_configs = {}
        configs = {
            k: v.value
            for k, v in mt_rest_obj.custom_configs.items()
            if v.config_value_type == ConfigValueType.STRING.value
        }

    def is_custom_strong_type(self):
        return self.custom_type is not None

        secrets = {
            k: v.value
            for k, v in mt_rest_obj.custom_configs.items()
            if v.config_value_type == ConfigValueType.SECRET.value
        }

        return cls(
            name=mt_rest_obj.connection_name,
            configs=configs,
            secrets=secrets,
            expiry_time=mt_rest_obj.expiry_time,
            created_date=mt_rest_obj.created_date,
            last_modified_date=mt_rest_obj.last_modified_date,
        )


    def convert_to_custom_strong_type_connection(self):
        module_name = self.configs.get(CustomStrongTypeConnectionConfigs.FULL_MODULE)
        custom_type_class_name = self.configs.get(CustomStrongTypeConnectionConfigs.FULL_TYPE)
        import importlib

        module = importlib.import_module(module_name)
        custom_defined_connection_class = getattr(module, custom_type_class_name)

        instance_dict = {}
        for key, value in self.configs.items():
            if key not in [CustomStrongTypeConnectionConfigs.FULL_MODULE, CustomStrongTypeConnectionConfigs.FULL_TYPE]:
                instance_dict[key] = value
        for key, value in self.secrets.items():
            instance_dict[key] = value
        connection_instance = custom_defined_connection_class(**instance_dict)

        return connection_instance

    @classmethod
    def convert_strong_type_to_custom(cls, custom_str_type_connection: _Connection):
        attributes = copy.copy(vars(custom_str_type_connection))
        attributes["module"] = PROMPTFLOW_CONNECTIONS
        # update configs
        configs = {}
        configs.update({CustomStrongTypeConnectionConfigs.FULL_TYPE: custom_str_type_connection.__class__.__name__})
        configs.update({CustomStrongTypeConnectionConfigs.FULL_MODULE: custom_str_type_connection.__module__})
        configs.update(**custom_str_type_connection.configs)

        attributes["configs"] = configs
        attributes["custom_type"] = custom_str_type_connection.__class__.__name__
        custom_connection = CustomConnection(**attributes)
        return custom_connection


_supported_types = {
    v.TYPE.value: v
    for v in globals().values()
    if isinstance(v, type) and issubclass(v, _Connection) and not v.__name__.startswith("_")
}
