# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import time

import jwt

from promptflow.core._connection_provider._utils import get_arm_token


class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class ArmTokenCache(metaclass=SingletonMeta):
    TOKEN_REFRESH_THRESHOLD_SECS = 300

    def __init__(self):
        self._cache = {}

    def _is_token_valid(self, entry):
        current_time = time.time()
        return (entry["expires_at"] - current_time) >= self.TOKEN_REFRESH_THRESHOLD_SECS

    def get_token(self, credential):
        if credential in self._cache:
            entry = self._cache[credential]
            if self._is_token_valid(entry):
                return entry["token"]

        token = self._fetch_token(credential)
        decoded_token = jwt.decode(token, options={"verify_signature": False, "verify_aud": False})
        expiration_time = decoded_token.get("exp", time.time())
        self._cache[credential] = {"token": token, "expires_at": expiration_time}
        return token

    def _fetch_token(self, credential):
        return get_arm_token(credential=credential)
