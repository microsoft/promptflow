from typing import Dict, Optional

from promptflow._core.singleton import Singleton


class ConnectionProvider(Singleton):
    def __init__(self, connection: Optional[Dict] = None):
        self._connection = connection or {}

    @classmethod
    def init(cls, connection: Optional[Dict] = None):
        return cls(connection=connection)

    def get_connections(self):
        return self._connection
