# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

__path__ = __import__("pkgutil").extend_path(__path__, __name__)

# below imports are temporary before `promptflow` layering as several sub-packages
# without these lines, users will run into breaking change before we expect them to face it
# for example, `from promptflow import PFClient` will fail
# expect to remove this and only reserve the namespace packages line
try:
    from promptflow._core.metric_logger import log_metric

    # flake8: noqa
    from promptflow._core.tool import ToolProvider, tool

    # control plane sdk functions
    from promptflow._sdk._load_functions import load_flow, load_run

    from ._sdk._pf_client import PFClient
    from ._version import VERSION

    # backward compatibility
    log_flow_metric = log_metric

    __version__ = VERSION

    __all__ = ["PFClient", "load_flow", "load_run", "log_metric", "ToolProvider", "tool"]

except ImportError:
    pass
