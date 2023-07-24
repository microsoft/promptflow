# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

__path__ = __import__("pkgutil").extend_path(__path__, __name__)  # type: ignore

from ._version import VERSION
from .core.metric_logger import log_metric

# flake8: noqa
from .core.tool import ToolProvider, tool

# control plane sdk functions
from .sdk._pf_client import PFClient
from .sdk._run_functions import get_details, get_metrics, run, stream, visualize

# backward compatibility
log_flow_metric = log_metric

__version__ = VERSION
