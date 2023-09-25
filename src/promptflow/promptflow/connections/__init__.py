# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from dataclasses import dataclass, is_dataclass

from promptflow._core.tools_manager import register_connections
from promptflow._sdk.entities import (
    AzureContentSafetyConnection,
    AzureOpenAIConnection,
    CognitiveSearchConnection,
    CustomConnection,
    FormRecognizerConnection,
    OpenAIConnection,
    SerpConnection,
    CustomStrongTypeConnection,
)
from promptflow._sdk.entities._connection import _Connection
from promptflow.contracts.types import Secret


@dataclass
class BingConnection:
    api_key: Secret
    url: str = "https://api.bing.microsoft.com/v7.0/search"


# We should use unified connection class everywhere.
# Do not add new connection class definition directly here.
# !!!Attention!!!: Do not add external package connections here.

__all__ = [
    "OpenAIConnection",
    "AzureOpenAIConnection",
    "AzureContentSafetyConnection",
    "SerpConnection",
    "CognitiveSearchConnection",
    "FormRecognizerConnection",
    "CustomConnection",
    "CustomStrongTypeConnection",
]

register_connections(
    [v for v in globals().values() if is_dataclass(v) or (isinstance(v, type) and issubclass(v, _Connection))]
)
