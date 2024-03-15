# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from contextvars import ContextVar
from typing import Type, TypeVar

T = TypeVar("T")


class ThreadLocalSingleton:
    # Use context variable to enable thread local singleton
    # See reference: https://docs.python.org/3/library/contextvars.html#contextvars.ContextVar
    CONTEXT_VAR_NAME = "ThreadLocalSingleton"
    context_var = ContextVar(CONTEXT_VAR_NAME, default=None)

    @classmethod
    def active_instance(cls: Type[T]) -> T:
        return cls.context_var.get()

    @classmethod
    def active(cls) -> bool:
        return cls.active_instance() is not None

    def _activate_in_context(self, force=False):
        instance = self.active_instance()
        if instance is not None and instance is not self and not force:
            raise NotImplementedError(f"Cannot set active since there is another active instance: {instance}")
        self.context_var.set(self)

    def _deactivate_in_context(self):
        self.context_var.set(None)
