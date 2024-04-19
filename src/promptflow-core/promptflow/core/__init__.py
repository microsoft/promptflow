# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
__path__ = __import__("pkgutil").extend_path(__path__, __name__)  # type: ignore

from promptflow._core.metric_logger import log_metric

# flake8: noqa
from promptflow._core.tool import ToolProvider, tool
from promptflow.core._flow import AsyncFlow, AsyncPrompty, Flow, Prompty
from promptflow.core._model_configuration import (
    AzureOpenAIModelConfiguration,
    ModelConfiguration,
    OpenAIModelConfiguration,
)

from ._version import __version__

# backward compatibility
log_flow_metric = log_metric

__all__ = [
    "log_metric",
    "ToolProvider",
    "tool",
    "Flow",
    "AsyncFlow",
    "Prompty",
    "AsyncPrompty",
    "ModelConfiguration",
    "OpenAIModelConfiguration",
    "AzureOpenAIModelConfiguration",
    "__version__",
]
