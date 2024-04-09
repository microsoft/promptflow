# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from dataclasses import fields, is_dataclass
from typing import Any, Dict

from promptflow._constants import CONNECTION_NAME_PROPERTY, CONNECTION_SECRET_KEYS, CustomStrongTypeConnectionConfigs
from promptflow._utils.utils import try_import
from promptflow.contracts.tool import ConnectionType
from promptflow.contracts.types import Secret

from ._connection_provider import ConnectionProvider


class DictConnectionProvider(ConnectionProvider):
    """Connection provider based on dict, core scenario: cloud submission."""

    def __init__(self, _dict: Dict[str, dict]):
        self._connections_dict = _dict or {}
        self._connections = self._build_connections(self._connections_dict)

    @classmethod
    def _build_connections(cls, _dict: Dict[str, dict]):
        """Build connection dict."""
        from promptflow._core.tools_manager import connections as cls_mapping

        cls.import_requisites(_dict)
        connections = {}  # key to connection object
        for key, connection_dict in _dict.items():
            typ = connection_dict.get("type")
            if typ not in cls_mapping:
                supported = [key for key in cls_mapping.keys() if not key.startswith("_")]
                raise ValueError(f"Unknown connection {key!r} type {typ!r}, supported are {supported}.")
            value = connection_dict.get("value", {})
            connection_class = cls_mapping[typ]

            from promptflow.connections import CustomConnection

            if connection_class is CustomConnection:
                # Note: CustomConnection definition can not be got, secret keys will be provided in connection dict.
                secret_keys = connection_dict.get("secret_keys", [])
                secrets = {k: v for k, v in value.items() if k in secret_keys}
                configs = {k: v for k, v in value.items() if k not in secrets}
                connection_value = connection_class(configs=configs, secrets=secrets, name=key)
                if CustomStrongTypeConnectionConfigs.PROMPTFLOW_TYPE_KEY in configs:
                    connection_value.custom_type = configs[CustomStrongTypeConnectionConfigs.PROMPTFLOW_TYPE_KEY]
            else:
                """
                Note: Ignore non exists keys of connection class,
                because there are some keys just used by UX like resource id, while not used by backend.
                """
                if is_dataclass(connection_class):
                    # Do not delete this branch, as promptflow_vectordb.connections is dataclass type.
                    cls_fields = {f.name: f for f in fields(connection_class)}
                    connection_value = connection_class(**{k: v for k, v in value.items() if k in cls_fields})
                    secret_keys = [f.name for f in cls_fields.values() if f.type == Secret]
                else:
                    connection_value = connection_class(**{k: v for k, v in value.items()})
                    if hasattr(connection_value, "name"):
                        connection_value.name = key
                    secrets = getattr(connection_value, "secrets", {})
                    secret_keys = list(secrets.keys()) if isinstance(secrets, dict) else []
            # Set secret keys for log scrubbing
            setattr(connection_value, CONNECTION_SECRET_KEYS, secret_keys)
            # Use this hack to make sure serialization works
            setattr(connection_value, CONNECTION_NAME_PROPERTY, key)
            connections[key] = connection_value
        return connections

    @classmethod
    def import_requisites(cls, _dict: Dict[str, dict]):
        """Import connection required modules."""
        modules = set()
        for key, connection_dict in _dict.items():
            module = connection_dict.get("module")
            if module:
                modules.add(module)
        for module in modules:
            # Suppress import error, as we have legacy module promptflow.tools.connections.
            try_import(module, f"Import connection module {module!r} failed.", raise_error=False)

    def get(self, name: str) -> Any:
        if isinstance(name, str):
            return self._connections.get(name)
        elif ConnectionType.is_connection_value(name):
            return name
        return None
