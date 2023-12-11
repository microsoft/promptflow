# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from enum import Enum
from promptflow._sdk._serving.extension.default_extension import AppExtension


class ExtensionType(Enum):
    """Extension type used to identify which extension to load in serving app."""

    Default = "local"
    AzureML = "azureml"


class ExtensionFactory:
    """ExtensionFactory is used to create extension based on extension type."""

    @staticmethod
    def create_extension(extension_type: ExtensionType, logger, **kwargs) -> AppExtension:
        """Create extension based on extension type."""
        if extension_type == ExtensionType.AzureML:
            from promptflow._sdk._serving.extension.azureml_extension import AzureMLExtension

            return AzureMLExtension(logger=logger, **kwargs)
        else:
            from promptflow._sdk._serving.extension.default_extension import DefaultAppExtension

            return DefaultAppExtension(logger=logger, **kwargs)
