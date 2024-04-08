# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os

from .simulator.simulator import Simulator  # pylint: disable=wrong-import-position

_template_dir = os.path.join(os.path.dirname(__file__), "templates")
__all__ = ["Simulator"]
