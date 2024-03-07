# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

__path__ = __import__("pkgutil").extend_path(__path__, __name__)  # type: ignore

from ._start_trace import start_trace
from ._trace import trace

__all__ = ["start_trace", "trace"]
