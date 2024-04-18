# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from promptflow.core._serving.extension.default_extension import AppExtension
from promptflow.core._serving.extension.extension_type import ExtensionType


class ExtensionFactory:
    """ExtensionFactory is used to create extension based on extension type."""

    @staticmethod
    def create_extension(logger, **kwargs) -> AppExtension:
        """Create extension based on extension type."""
        extension_type_str = kwargs.pop("extension_type", None)
        logger.info(f"Create extension with type: {extension_type_str}")
        if not extension_type_str:
            extension_type_str = ExtensionType.DEFAULT.value
        extension_type = ExtensionType(extension_type_str.lower())

        if extension_type == ExtensionType.AZUREML:
            logger.info("Enable AzureML extension.")
            from promptflow.core._serving.extension.azureml_extension import AzureMLExtension

            return AzureMLExtension(logger=logger, **kwargs)
        else:
            from promptflow.core._serving.extension.default_extension import DefaultAppExtension

            return DefaultAppExtension(logger=logger, **kwargs)
