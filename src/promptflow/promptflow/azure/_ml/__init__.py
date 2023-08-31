# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

"""
This file stores functions and objects that will be used in prompt-flow sdk.
DO NOT change the module names in "all" list, add new modules if needed.
"""


class _DummyCallableClassForLazyImportError:
    """This class is used to put off ImportError until the imported class or function is called."""

    @classmethod
    def _get_message(cls):
        return "azure-ai-ml is not installed. Please install azure-ai-ml to use this feature."

    def __init__(self, *args, **kwargs):
        raise ImportError(self._get_message())

    def __call__(self, *args, **kwargs):
        raise ImportError(self._get_message())


# TODO: avoid import azure.ai.ml if promptflow.azure.configure is not called
try:
    from azure.ai.ml import MLClient, load_component
    from azure.ai.ml.entities import Component
    from azure.ai.ml.entities._assets import Code
    from azure.ai.ml.entities._component._additional_includes import AdditionalIncludesMixin
    from azure.ai.ml.entities._load_functions import load_common
except ImportError:

    class load_component(_DummyCallableClassForLazyImportError):
        pass

    class Component(_DummyCallableClassForLazyImportError):
        pass

    class MLClient(_DummyCallableClassForLazyImportError):
        pass

    class load_common(_DummyCallableClassForLazyImportError):
        pass

    class Code(_DummyCallableClassForLazyImportError):
        pass

    class AdditionalIncludesMixin(_DummyCallableClassForLazyImportError):
        pass


__all__ = [
    "load_component",
    "Component",
    "MLClient",
    "load_common",
    "Code",
    "AdditionalIncludesMixin",
]
