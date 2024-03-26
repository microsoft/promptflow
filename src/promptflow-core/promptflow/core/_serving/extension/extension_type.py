# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from enum import Enum


class ExtensionType(Enum):
    """Extension type used to identify which extension to load in serving app."""

    DEFAULT = "local"
    AZUREML = "azureml"
