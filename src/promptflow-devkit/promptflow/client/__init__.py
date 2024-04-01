# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
__path__ = __import__("pkgutil").extend_path(__path__, __name__)  # type: ignore


_imported_attr = {}


# control plane sdk functions
# Use lazy import to avoid circular import
# Circular path: PFClient -> UserAgent -> client._version -> client.__init__ -> PFClient
def __getattr__(name):
    if name in _imported_attr:
        return _imported_attr[name]
    if name in ["PFClient", "load_run", "load_flow"]:
        from promptflow._sdk._load_functions import load_flow, load_run  # noqa: F401
        from .._sdk._pf_client import PFClient  # noqa: F401

        _imported_attr[name] = locals()[name]
        return _imported_attr[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
