# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import abc
import copy
import importlib
import json
from os import PathLike
from pathlib import Path
from typing import Dict, Union

from marshmallow import INCLUDE

from promptflow._constants import ConnectionType, CustomStrongTypeConnectionConfigs
from promptflow._sdk._constants import (
    BASE_PATH_CONTEXT_KEY,
    PARAMS_OVERRIDE_KEY,
    SCHEMA_KEYS_CONTEXT_CONFIG_KEY,
    SCHEMA_KEYS_CONTEXT_SECRET_KEY,
    SCRUBBED_VALUE,
    SCRUBBED_VALUE_USER_INPUT,
    ConfigValueType,
)
from promptflow._sdk._errors import ConnectionClassNotFoundError, SDKError, UnsecureConnectionError
from promptflow._sdk._orm.connection import Connection as ORMConnection
from promptflow._sdk._utilities.general_utils import (
    decrypt_secret_value,
    encrypt_secret_value,
    find_type_in_override,
    print_yellow_warning,
)
from promptflow._sdk.entities._yaml_translatable import YAMLTranslatableMixin
from promptflow._sdk.schemas._connection import (
    AzureAIServicesConnectionSchema,
    AzureContentSafetyConnectionSchema,
    AzureOpenAIConnectionSchema,
    CognitiveSearchConnectionSchema,
    CustomConnectionSchema,
    CustomStrongTypeConnectionSchema,
    FormRecognizerConnectionSchema,
    OpenAIConnectionSchema,
    QdrantConnectionSchema,
    SerpConnectionSchema,
    ServerlessConnectionSchema,
    WeaviateConnectionSchema,
)
from promptflow._utils.logger_utils import LoggerFactory
from promptflow._utils.utils import snake_to_camel
from promptflow.contracts.types import Secret
from promptflow.core._connection import AzureAIServicesConnection as _CoreAzureAIServicesConnection
from promptflow.core._connection import AzureContentSafetyConnection as _CoreAzureContentSafetyConnection
from promptflow.core._connection import AzureOpenAIConnection as _CoreAzureOpenAIConnection
from promptflow.core._connection import CognitiveSearchConnection as _CoreCognitiveSearchConnection
from promptflow.core._connection import CustomConnection as _CoreCustomConnection
from promptflow.core._connection import CustomStrongTypeConnection as _CoreCustomStrongTypeConnection
from promptflow.core._connection import FormRecognizerConnection as _CoreFormRecognizerConnection
from promptflow.core._connection import OpenAIConnection as _CoreOpenAIConnection
from promptflow.core._connection import QdrantConnection as _CoreQdrantConnection
from promptflow.core._connection import SerpConnection as _CoreSerpConnection
from promptflow.core._connection import ServerlessConnection as _CoreServerlessConnection
from promptflow.core._connection import WeaviateConnection as _CoreWeaviateConnection
from promptflow.core._connection import _Connection as _CoreConnection
from promptflow.core._connection import _StrongTypeConnection as _CoreStrongTypeConnection
from promptflow.exceptions import UserErrorException, ValidationException

logger = LoggerFactory.get_logger(name=__name__)
PROMPTFLOW_CONNECTIONS = "promptflow.connections"


class _Connection(_CoreConnection, YAMLTranslatableMixin):
    SUPPORTED_TYPES = {}

    def __str__(self):
        """Override this function to scrub secrets in connection when print."""
        obj_for_dump = copy.deepcopy(self)
        # Scrub secrets.
        obj_for_dump.secrets = {k: SCRUBBED_VALUE for k in obj_for_dump.secrets}
        try:
            return obj_for_dump._to_yaml()
        except BaseException:  # pylint: disable=broad-except
            return super(YAMLTranslatableMixin, self).__str__()

    @classmethod
    def _casting_type(cls, typ):
        type_dict = {
            "azure_open_ai": ConnectionType.AZURE_OPEN_AI.value,
            "open_ai": ConnectionType.OPEN_AI.value,
            "azure_ai_services": ConnectionType.AZURE_AI_SERVICES.value,
        }

        if typ in type_dict:
            return type_dict.get(typ)
        return snake_to_camel(typ)

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
            raise ValidationException(
                f"Connection {self.name!r} secrets {invalid_secrets} value invalid, please fill them."
            )
        return encrypt_secrets

    @classmethod
    def _load_from_dict(cls, data: Dict, context: Dict, additional_message: str = None, **kwargs):
        schema_cls = cls._get_schema_cls()
        try:
            loaded_data = schema_cls(context=context).load(data, **kwargs)
        except Exception as e:
            raise SDKError(f"Load connection failed with {str(e)}. f{(additional_message or '')}.")
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
            raise ValidationException("type is required for connection.")
        type_str = cls._casting_type(type_str)
        type_cls = cls.SUPPORTED_TYPES.get(type_str)
        if type_cls is None:
            raise ValidationException(
                f"Connection type {type_str!r} is not supported. "
                f"Supported types are: {list(cls.SUPPORTED_TYPES.keys())}"
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
    def _from_core_connection(cls, core_conn) -> "_Connection":
        if isinstance(core_conn, _Connection):
            # Already a sdk connection, return.
            return core_conn
        sdk_conn_mapping = _Connection.SUPPORTED_TYPES
        sdk_conn_cls = sdk_conn_mapping.get(core_conn.type)
        if sdk_conn_cls is None:
            raise ConnectionClassNotFoundError(
                f"Correspond sdk connection type not found for core connection type: {core_conn.type!r}, "
                f"please re-install the 'promptflow' package."
            )
        common_args = {
            "name": core_conn.name,
            "module": core_conn.module,
            "expiry_time": core_conn.expiry_time,
            "created_date": core_conn.created_date,
            "last_modified_date": core_conn.last_modified_date,
        }
        if sdk_conn_cls is CustomConnection:
            return sdk_conn_cls(configs=core_conn.configs, secrets=core_conn.secrets, **common_args)
        return sdk_conn_cls(**dict(core_conn), **common_args)

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
        **kwargs,
    ) -> "_Connection":
        """Load a connection object from a yaml file.

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
        :return: Loaded a connection object.
        :rtype: ~promptflow._sdk.entities._connection._Connection
        """
        data = data or {}
        params_override = params_override or []
        context = {
            BASE_PATH_CONTEXT_KEY: Path(yaml_path).parent if yaml_path else Path("../../azure/_entities/"),
            PARAMS_OVERRIDE_KEY: params_override,
        }
        connection_type, type_str = cls._resolve_cls_and_type(data, params_override)
        connection = connection_type._load_from_dict(
            data=data,
            context=context,
            unknown=INCLUDE,
            additional_message=(
                f"If you are trying to configure a connection that is not of type {type_str}, please specify "
                "the correct connection type in the 'type' property."
            ),
            **kwargs,
        )
        return connection


class _StrongTypeConnection(_CoreStrongTypeConnection, _Connection):
    def _to_orm_object(self):
        # Both keys & secrets will be stored in configs for strong type connection.
        secrets = self._validate_and_encrypt_secrets()
        return ORMConnection(
            connectionName=self.name,
            connectionType=self.type,
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
        configs = mt_rest_obj.configs or {}
        # For not ARM strong type connection, e.g. OpenAI, api_key will not be returned, but is required argument.
        # For ARM strong type connection, api_key will be None and missing when conn._to_dict(), so set a scrubbed one.
        configs.update({"api_key": SCRUBBED_VALUE})
        obj = type_cls(
            name=mt_rest_obj.connection_name,
            expiry_time=mt_rest_obj.expiry_time,
            created_date=mt_rest_obj.created_date,
            last_modified_date=mt_rest_obj.last_modified_date,
            **configs,
        )
        return obj


class AzureOpenAIConnection(_CoreAzureOpenAIConnection, _StrongTypeConnection):
    __doc__ = _CoreAzureOpenAIConnection.__doc__
    DATA_CLASS = _CoreAzureOpenAIConnection

    @classmethod
    def _get_schema_cls(cls):
        return AzureOpenAIConnectionSchema


class OpenAIConnection(_CoreOpenAIConnection, _StrongTypeConnection):
    __doc__ = _CoreOpenAIConnection.__doc__
    DATA_CLASS = _CoreOpenAIConnection

    @classmethod
    def _get_schema_cls(cls):
        return OpenAIConnectionSchema


class ServerlessConnection(_CoreServerlessConnection, _StrongTypeConnection):
    __doc__ = _CoreServerlessConnection.__doc__
    DATA_CLASS = _CoreServerlessConnection

    @classmethod
    def _get_schema_cls(cls):
        return ServerlessConnectionSchema


class SerpConnection(_CoreSerpConnection, _StrongTypeConnection):
    __doc__ = _CoreSerpConnection.__doc__
    DATA_CLASS = _CoreSerpConnection

    @classmethod
    def _get_schema_cls(cls):
        return SerpConnectionSchema


class QdrantConnection(_CoreQdrantConnection, _StrongTypeConnection):
    __doc__ = _CoreQdrantConnection.__doc__
    DATA_CLASS = _CoreQdrantConnection

    @classmethod
    def _get_schema_cls(cls):
        return QdrantConnectionSchema


class WeaviateConnection(_CoreWeaviateConnection, _StrongTypeConnection):
    __doc__ = _CoreWeaviateConnection.__doc__
    DATA_CLASS = _CoreWeaviateConnection

    @classmethod
    def _get_schema_cls(cls):
        return WeaviateConnectionSchema


class CognitiveSearchConnection(_CoreCognitiveSearchConnection, _StrongTypeConnection):
    __doc__ = _CoreCognitiveSearchConnection.__doc__
    DATA_CLASS = _CoreCognitiveSearchConnection

    @classmethod
    def _get_schema_cls(cls):
        return CognitiveSearchConnectionSchema


class AzureAIServicesConnection(_CoreAzureAIServicesConnection, _StrongTypeConnection):
    __doc__ = _CoreAzureAIServicesConnection.__doc__
    DATA_CLASS = _CoreAzureAIServicesConnection

    @classmethod
    def _get_schema_cls(cls):
        return AzureAIServicesConnectionSchema


class AzureContentSafetyConnection(_CoreAzureContentSafetyConnection, _StrongTypeConnection):
    __doc__ = _CoreAzureContentSafetyConnection.__doc__
    DATA_CLASS = _CoreAzureContentSafetyConnection

    @classmethod
    def _get_schema_cls(cls):
        return AzureContentSafetyConnectionSchema


class FormRecognizerConnection(_CoreFormRecognizerConnection, AzureContentSafetyConnection):
    __doc__ = _CoreFormRecognizerConnection.__doc__
    DATA_CLASS = _CoreFormRecognizerConnection

    @classmethod
    def _get_schema_cls(cls):
        return FormRecognizerConnectionSchema


class CustomStrongTypeConnection(_CoreCustomStrongTypeConnection, _Connection):
    __doc__ = _CoreCustomStrongTypeConnection.__doc__
    DATA_CLASS = _CoreCustomStrongTypeConnection

    def _to_orm_object(self) -> ORMConnection:
        custom_connection = self._convert_to_custom()
        return custom_connection._to_orm_object()

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

    @classmethod
    def _get_schema_cls(cls):
        return CustomStrongTypeConnectionSchema

    @classmethod
    def _load_from_dict(cls, data: Dict, context: Dict, additional_message: str = None, **kwargs):
        schema_config_keys, schema_secret_keys = cls._get_custom_keys(data)
        context[SCHEMA_KEYS_CONTEXT_CONFIG_KEY] = schema_config_keys
        context[SCHEMA_KEYS_CONTEXT_SECRET_KEY] = schema_secret_keys

        return (super()._load_from_dict(data, context, additional_message, **kwargs))._convert_to_custom()


class CustomConnection(_CoreCustomConnection, _Connection):
    __doc__ = _CoreCustomConnection.__doc__
    DATA_CLASS = _CoreCustomConnection

    @classmethod
    def _get_schema_cls(cls):
        return CustomConnectionSchema

    @classmethod
    def _load_from_dict(cls, data: Dict, context: Dict, additional_message: str = None, **kwargs):
        # If context has params_override, it means the data would be updated by overridden values.
        # Provide CustomStrongTypeConnectionSchema if 'custom_type' in params_override, else CustomConnectionSchema.
        # For example:
        #   If a user updates an existing connection by re-upserting a connection file,
        #   the 'data' from DB is CustomConnection,
        #   but 'params_override' would actually contain custom strong type connection data.
        is_custom_strong_type = data.get(CustomStrongTypeConnectionConfigs.TYPE) or any(
            CustomStrongTypeConnectionConfigs.TYPE in d for d in context.get(PARAMS_OVERRIDE_KEY, [])
        )
        if is_custom_strong_type:
            return CustomStrongTypeConnection._load_from_dict(data, context, additional_message, **kwargs)

        return super()._load_from_dict(data, context, additional_message, **kwargs)

    def _to_orm_object(self):
        # Both keys & secrets will be set in custom configs with value type specified for custom connection.
        if not self.secrets:
            error = ValueError(
                "Secrets is required for custom connection, "
                "please use CustomConnection(configs={key1: val1}, secrets={key2: val2}) "
                "to initialize custom connection."
            )
            raise UserErrorException(message=str(error), error=error)
        custom_configs = {
            k: {"configValueType": ConfigValueType.STRING.value, "value": v} for k, v in self.configs.items()
        }
        encrypted_secrets = self._validate_and_encrypt_secrets()
        custom_configs.update(
            {k: {"configValueType": ConfigValueType.SECRET.value, "value": v} for k, v in encrypted_secrets.items()}
        )

        return ORMConnection(
            connectionName=self.name,
            connectionType=self.type,
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
            if k == CustomStrongTypeConnectionConfigs.PROMPTFLOW_TYPE_KEY:
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


# Note: Do not import this from core connection.
# As we need the class here.
_Connection.SUPPORTED_TYPES = {
    v.TYPE: v
    for v in globals().values()
    if isinstance(v, type) and issubclass(v, _Connection) and not v.__name__.startswith("_")
}
