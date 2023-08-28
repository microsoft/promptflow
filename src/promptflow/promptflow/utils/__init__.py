# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import importlib
import sys
from types import ModuleType


class LazyModule(ModuleType):
    def __init__(self, name, mod_name):
        super().__init__(name)
        self.__mod_name = mod_name
        self.__package = name.rpartition(".")[0]

    def __getattr__(self, attr):
        if "_lazy_module" not in self.__dict__:
            self._lazy_module = importlib.import_module(self.__mod_name, self.__package)
        return getattr(self._lazy_module, attr)


sys.modules["promptflow.utils"] = LazyModule("promptflow.utils", "promptflow._utils")
