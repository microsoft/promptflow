# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import importlib.metadata

try:
    __version__ = importlib.metadata.version("promptflow-evals")
except BaseException:
    __version__ = '0.3.1.rc1'

VERSION: str = __version__
