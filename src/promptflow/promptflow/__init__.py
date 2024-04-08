# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
__path__ = __import__("pkgutil").extend_path(__path__, __name__)  # type: ignore

import logging
from typing import Any

try:
    # Note: Keep old import ensure import order
    # Keep old import as hidden to let __getattr__ works
    from promptflow._core.metric_logger import log_metric as _log_metric
    from promptflow._core.tool import ToolProvider as _ToolProvider
    from promptflow._core.tool import tool as _tool

    # control plane sdk functions
    from promptflow._sdk._load_functions import load_flow as _load_flow
    from promptflow._sdk._load_functions import load_run as _load_run
    from promptflow._sdk._pf_client import PFClient as _PFClient
except ImportError as e:
    raise Exception(
        "Promptflow may not installed correctly. If you are upgrading from 'promptflow<1.8.0' to 'promptflow>=1.8.0', "
        "please run 'pip uninstall -y promptflow promptflow-core promptflow-devkit promptflow-azure', "
        "then 'pip install promptflow>=1.8.0'. Reach "
        "https://microsoft.github.io/promptflow/how-to-guides/faq.html#promptflow-1-8-0-upgrade-guide "
        "for more information."
    ) from e


# flake8: noqa
from ._version import VERSION

__version__ = VERSION

_core_attr = ["log_metric", "ToolProvider", "tool"]
_client_attr = ["PFClient", "load_flow", "load_run"]
_imported_attr = {}


def _log_warning(name, target_module, target_name=None) -> Any:
    target_name = name if not target_name else target_name
    legacy_import = f"from promptflow import {name}"
    new_import = f"from promptflow.{target_module} import {target_name}"
    logging.warning(f"{legacy_import!r} is deprecated and will be removed in the future. Use {new_import!r} instead.")


def __getattr__(name):
    if name in _imported_attr:
        return _imported_attr[name]
    if name in _core_attr:
        from promptflow.core import ToolProvider, log_metric, tool

        _log_warning(name, "core")
        _imported_attr[name] = locals()[name]
        return _imported_attr[name]
    if name in _client_attr:
        # control plane sdk functions
        from promptflow.client import PFClient, load_flow, load_run

        _log_warning(name, "client")
        _imported_attr[name] = locals()[name]
        return _imported_attr[name]
    if name == "log_flow_metric":
        # backward compatibility
        from promptflow.core import log_metric

        _log_warning(name, "core", "log_metric")
        _imported_attr[name] = log_metric
        return _imported_attr[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
