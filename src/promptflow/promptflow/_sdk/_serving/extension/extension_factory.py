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
    def create_extension(logger, **kwargs) -> AppExtension:
        """Create extension based on extension type."""
        extension_type_str = kwargs.get("extension_type", ExtensionType.Default.value)
        if not extension_type_str:
            extension_type_str = ExtensionType.Default.value
        extension_type = ExtensionType(extension_type_str.lower())

        if extension_type == ExtensionType.AzureML:
            logger.info("Enable AzureML extension.")
            from promptflow._sdk._serving.extension.azureml_extension import AzureMLExtension

            return AzureMLExtension(logger=logger, **kwargs)
        else:
            from promptflow._sdk._serving.extension.default_extension import DefaultAppExtension

            return DefaultAppExtension(logger=logger, **kwargs)
