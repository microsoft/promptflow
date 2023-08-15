# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

__path__ = __import__("pkgutil").extend_path(__path__, __name__)  # type: ignore

import importlib
import sys
from pathlib import Path
from types import ModuleType

from promptflow import _core


class LazyModule(ModuleType):
    def __init__(self, name, mod_name):
        super().__init__(name)
        self.__mod_name = mod_name
        self.__package = name.rpartition(".")[0]

    def __getattr__(self, attr):
        if "_lazy_module" not in self.__dict__:
            self._lazy_module = importlib.import_module(self.__mod_name, self.__package)
        return getattr(self._lazy_module, attr)


# re-import for the module for old reference
# Below block shall be removed once other service updated the modules with the new import
sys.modules["promptflow.core"] = LazyModule("promptflow.core", "promptflow._core")
for f in Path(_core.__file__).parent.iterdir():
    sys.modules[f"promptflow.core.{f.stem}"] = LazyModule(
        "promptflow.core" + f.stem, "promptflow._core." + f.stem
    )
