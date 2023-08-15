# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from dataclasses import dataclass, is_dataclass

from promptflow._constants import CONNECTION_SECRET_KEYS
from promptflow._core.tools_manager import register_connections
from promptflow.contracts.types import Secret


@dataclass
class BingConnection:
    api_key: Secret
    url: str = "https://api.bing.microsoft.com/v7.0/search"


@dataclass
class OpenAIConnection:
    api_key: Secret
    organization: str = None


@dataclass
class AzureOpenAIConnection:
    api_key: Secret
    api_base: str
    api_type: str = "azure"
    api_version: str = "2023-07-01-preview"


@dataclass
class AzureContentSafetyConnection:
    api_key: Secret
    endpoint: str
    api_version: str = "2023-04-30-preview"


@dataclass
class SerpConnection:
    api_key: Secret


@dataclass
class CognitiveSearchConnection:
    api_key: Secret
    api_base: str
    api_version: str = "2023-07-01-Preview"


@dataclass
class FormRecognizerConnection:
    api_key: Secret
    endpoint: str
    api_version: str = "2023-07-31"


class CustomConnection(dict):
    def __init__(self, *args, **kwargs):
        # record secret keys if init from local
        for k, v in kwargs.items():
            if isinstance(v, Secret):
                self._set_secret(k)
        super().__init__(*args, **kwargs)

    def __getattr__(self, item):
        if item in self:
            return self.__getitem__(item)
        return super().__getattribute__(item)

    def is_secret(self, item):
        secret_keys = getattr(self, CONNECTION_SECRET_KEYS, [])
        return item in secret_keys

    def _set_secret(self, item):
        secret_keys = getattr(self, CONNECTION_SECRET_KEYS, [])
        secret_keys.append(item)
        setattr(self, CONNECTION_SECRET_KEYS, secret_keys)


register_connections([v for v in globals().values() if is_dataclass(v) or v is CustomConnection])
