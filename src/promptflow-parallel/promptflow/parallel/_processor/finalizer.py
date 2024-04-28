# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from abc import ABC, abstractmethod
from contextlib import ExitStack
from typing import List

from promptflow.parallel._model import Row


class Finalizer(ABC):
    @property
    @abstractmethod
    def process_enabled(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def process(self, row: Row) -> None:
        raise NotImplementedError

    def __enter__(self) -> "Finalizer":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class CompositeFinalizer(Finalizer):
    def __init__(self, finalizers: List[Finalizer]):
        self._finalizers = finalizers
        self._exit_stack = ExitStack()

    @property
    def process_enabled(self) -> bool:
        return next(self._enabled_finalizers, None) is not None

    def process(self, row: Row):
        for finalizer in self._enabled_finalizers:
            finalizer.process(row)

    @property
    def _enabled_finalizers(self):
        for finalizer in self._finalizers:
            if finalizer.process_enabled:
                yield finalizer

    def __enter__(self):
        for finalizer in self._finalizers:
            self._exit_stack.enter_context(finalizer)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._exit_stack.__exit__(exc_type, exc_val, exc_tb)
