# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from dataclasses import dataclass
from typing import Any, Dict, Optional
from azure.ai.ml._utils.utils import camel_to_snake
from promptflow.entities import AzureOpenAIConnection


@dataclass
class AzureOpenAIModelConfiguration:
    """Configuration for an Azure OpenAI model.

    :param api_base: The base URL for the OpenAI API.
    :type api_base: str
    :param api_key: The OpenAI API key.
    :type api_key: str
    :param api_version: The OpenAI API version.
    :type api_version: Optional[str]
    :param model_name: The name of the model.
    :type model_name: str
    :param deployment_name: The name of the deployment.
    :type deployment_name: str
    :param model_kwargs: Additional keyword arguments for the model.
    :type model_kwargs: Dict[str, Any]
    """
    api_base: str
    api_key: str
    api_version: Optional[str]
    model_name: str
    deployment_name: str
    model_kwargs: Dict[str, Any] = None

