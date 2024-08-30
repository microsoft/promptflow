# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

"""Tooling for model evaluation"""

from ._identity_manager import ManagedIdentityAPITokenManager, PlainTokenManager, TokenScope
from ._proxy_completion_model import ProxyChatCompletionsModel
from ._rai_client import RAIClient
from ._template_handler import CONTENT_HARM_TEMPLATES_COLLECTION_KEY, AdversarialTemplateHandler
from .models import LLMBase, OpenAIChatCompletionsModel

__all__ = [
    "ManagedIdentityAPITokenManager",
    "PlainTokenManager",
    "TokenScope",
    "RAIClient",
    "AdversarialTemplateHandler",
    "CONTENT_HARM_TEMPLATES_COLLECTION_KEY",
    "ProxyChatCompletionsModel",
    "LLMBase",
    "OpenAIChatCompletionsModel",
]
