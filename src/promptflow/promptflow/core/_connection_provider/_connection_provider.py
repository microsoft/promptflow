# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from abc import ABC, abstractmethod
from typing import Any


class ConnectionProvider(ABC):
    @abstractmethod
    def get(self, name: str) -> Any:
        """Get connection by name."""
        raise NotImplementedError

    @classmethod
    def _init_from_env(cls):
        """Initialize the connection provider from environment variables."""
        pass
