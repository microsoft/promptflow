# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from promptflow._core.tools_manager import register_connections
from promptflow._sdk.entities import (
    AzureContentSafetyConnection,
    AzureOpenAIConnection,
    CognitiveSearchConnection,
    CustomConnection,
    FormRecognizerConnection,
    OpenAIConnection,
    SerpConnection,
)
from promptflow._sdk.entities._connection import _Connection

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
]

register_connections([v for v in globals().values() if (isinstance(v, type) and issubclass(v, _Connection))])
