from contextvars import ContextVar, Token
from typing import Any, Dict, Optional

from promptflow._core.thread_local_singleton import ThreadLocalSingleton


class ExecutionContextVars(ThreadLocalSingleton):
    """The context variables for execution."""

    CONTEXT_VAR_NAME = "ContextVars"
    context_var = ContextVar(CONTEXT_VAR_NAME, default=None)

    def __init__(self, vars: Optional[Dict[str, Any]] = None):
        self._context_vars: Dict[str, ContextVar] = {}
        self._tokens: Dict[str, Token] = {}
        if vars:
            for name, value in vars.items():
                self.set(name, value)

    @classmethod
    def start(cls, vars: Optional[Dict[str, Any]] = None):
        instance = cls(vars)
        instance._activate_in_context()
        return instance

    @classmethod
    def end(cls):
        instance = cls.active_instance()
        if instance:
            instance._reset_all()
            instance._deactivate_in_context()

    def set(self, name: str, value: Any):
        if name not in self._context_vars:
            self._context_vars[name] = ContextVar(name)
        self._tokens[name] = self._context_vars[name].set(value)

    def get(self, name: str, default: Optional[Any] = None):
        if name in self._context_vars:
            try:
                return self._context_vars[name].get()
            except LookupError:
                return default
        return default

    def _reset(self, name: str):
        if name in self._tokens:
            self._context_vars[name].reset(self._tokens[name])
            del self._tokens[name]

    def _reset_all(self):
        for name, token in self._tokens.items():
            if name in self._context_vars:
                self._context_vars[name].reset(token)
        self._tokens.clear()

    @classmethod
    def pop(cls, name: str, default: Optional[Any] = None) -> Any:
        """Pop the context variable, reset its value, and remove it from the manager."""

        instance = cls.active_instance()
        if not instance:
            return default

        if name in instance._context_vars:
            value = instance.get(name, default)
            instance._reset(name)
            del instance._context_vars[name]
            return value
        return default
