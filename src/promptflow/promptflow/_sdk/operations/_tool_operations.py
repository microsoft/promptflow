# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import contextlib
import json
from importlib.metadata import version
from os import PathLike
from pathlib import Path
from typing import Iterable, List, Tuple, Union

import yaml


class ToolOperations:
    """ToolOperations."""

    def __init__(self):
        pass

    def list(self) -> dict:
        """List toos."""
        pass

    def _generate_tool_meta(self):
        pass
