# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import copy
import json
import os
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any, Dict, List

from promptflow._constants import (
    CONNECTION_NAME_PROPERTY,
    CONNECTION_SECRET_KEYS,
    PROMPTFLOW_CONNECTIONS,
    CustomStrongTypeConnectionConfigs,
)
from promptflow._utils.utils import try_import
from promptflow.contracts.tool import ConnectionType
from promptflow.contracts.types import Secret


class ConnectionManager:
    """This class will be used for construction mode to run flow. Do not include it into tool code."""

    instance = None

    def __init__(self, _dict: Dict[str, dict] = None):
        if _dict is None and PROMPTFLOW_CONNECTIONS in os.environ:
            # !!! Important !!!: Do not leverage this environment variable in any production code, this is test only.
            if PROMPTFLOW_CONNECTIONS not in os.environ:
                raise ValueError(f"Required environment variable {PROMPTFLOW_CONNECTIONS!r} not set.")
            connection_path = Path(os.environ[PROMPTFLOW_CONNECTIONS]).resolve().absolute()
            if not connection_path.exists():
                raise ValueError(f"Connection file not exists. Path {connection_path.as_posix()}.")
            _dict = json.loads(open(connection_path).read())
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
    def init_from_env(cls):
        return ConnectionManager()

    def get(self, connection_info: Any) -> Any:
        """Get Connection by connection info.

        connection_info:
            connection name as string or connection object
        """
        if isinstance(connection_info, str):
            return self._connections.get(connection_info)
        elif ConnectionType.is_connection_value(connection_info):
            return connection_info
        return None

    def get_secret_list(self) -> List[str]:
        def secrets():
            for connection in self._connections.values():
                secret_keys = getattr(connection, CONNECTION_SECRET_KEYS, [])
                for secret_key in secret_keys:
                    yield getattr(connection, secret_key)

        return list(secrets())

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

    @staticmethod
    def is_legacy_connections(_dict: Dict[str, dict]):
        """Detect if is legacy connections. Legacy connections dict doesn't have module and type.
        So import requisites can not be performed. Only request from MT will hit this.

        Legacy connection example: {"aoai_config": {"api_key": "..."}}
        """
        has_module = any(isinstance(v, dict) and "module" in v for k, v in _dict.items())
        return not has_module

    def to_connections_dict(self) -> dict:
        """Get all connections and reformat to key-values format."""
        # Value returned: {"aoai_config": {"api_key": "..."}}
        return copy.deepcopy(self._connections_dict)
