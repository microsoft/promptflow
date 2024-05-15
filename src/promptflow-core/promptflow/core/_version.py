# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import importlib.metadata

try:
    __version__ = importlib.metadata.version("promptflow-core")
except BaseException:
    __version__ = '0.0.1.dev0'

VERSION: str = __version__
