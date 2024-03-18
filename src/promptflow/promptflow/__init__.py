# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
__path__ = __import__("pkgutil").extend_path(__path__, __name__)  # type: ignore

import logging
from typing import Any

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
