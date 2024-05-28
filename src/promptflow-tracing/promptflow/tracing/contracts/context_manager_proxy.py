from typing import ContextManager


class ContextManagerProxy:
    """A proxy for an context manager."""

    def __init__(self, obj):
        self._obj = obj

    def __enter__(self):
        if isinstance(self._obj, ContextManager):
            return self._obj.__enter__()
        else:
            raise AttributeError(f"{self._obj} is not a context manager.")

    def __exit__(self, exc_type, exc_value, traceback):
        if isinstance(self._obj, ContextManager):
            return self._obj.__exit__(exc_type, exc_value, traceback)
        else:
            raise AttributeError(f"{self._obj} is not a context manager.")
