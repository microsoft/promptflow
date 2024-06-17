import time

from promptflow.core._connection_provider._utils import get_arm_token


class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class ArmTokenCache(metaclass=SingletonMeta):
    DEFAULT_TTL_SECS = 1800

    def __init__(self):
        self._ttl_secs = self.DEFAULT_TTL_SECS
        self._cache = {}

    def _is_token_valid(self, entry):
        return time.time() < entry["expires_at"]

    def get_token(self, credential):
        if credential in self._cache:
            entry = self._cache[credential]
            if self._is_token_valid(entry):
                return entry["token"]

        token = self._fetch_token(credential)
        self._cache[credential] = {"token": token, "expires_at": time.time() + self._ttl_secs}
        return token

    def _fetch_token(self, credential):
        return get_arm_token(credential=credential)
