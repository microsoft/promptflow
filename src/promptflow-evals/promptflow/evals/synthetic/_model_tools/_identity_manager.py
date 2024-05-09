# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import asyncio
import os
import time
from abc import ABC, abstractmethod
from enum import Enum

from azure.identity import DefaultAzureCredential, ManagedIdentityCredential

AZURE_TOKEN_REFRESH_INTERVAL = 600  # seconds


class TokenScope(Enum):
    DEFAULT_AZURE_MANAGEMENT = "https://management.azure.com/.default"


class APITokenManager(ABC):
    def __init__(self, logger, auth_header="Bearer", credential=None):
        self.logger = logger
        self.auth_header = auth_header
        self._lock = None
        if credential is not None:
            self.credential = credential
        else:
            self.credential = self.get_aad_credential()
        self.token = None
        self.last_refresh_time = None

    @property
    def lock(self):
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def get_aad_credential(self):
        identity_client_id = os.environ.get("DEFAULT_IDENTITY_CLIENT_ID", None)
        if identity_client_id is not None:
            self.logger.info(f"Using DEFAULT_IDENTITY_CLIENT_ID: {identity_client_id}")
            credential = ManagedIdentityCredential(client_id=identity_client_id)
        else:
            self.logger.info("Environment variable DEFAULT_IDENTITY_CLIENT_ID is not set, using DefaultAzureCredential")
            credential = DefaultAzureCredential()
        return credential

    @abstractmethod
    async def get_token(self):
        pass


class ManagedIdentityAPITokenManager(APITokenManager):
    def __init__(self, token_scope, logger, **kwargs):
        super().__init__(logger, **kwargs)
        self.token_scope = token_scope

    def get_token(self):

        if (
            self.token is None
            or self.last_refresh_time is None
            or time.time() - self.last_refresh_time > AZURE_TOKEN_REFRESH_INTERVAL
        ):
            self.last_refresh_time = time.time()
            self.token = self.credential.get_token(self.token_scope.value).token
            self.logger.info("Refreshed Azure endpoint token.")

        return self.token


class PlainTokenManager(APITokenManager):
    def __init__(self, openapi_key, logger, **kwargs):
        super().__init__(logger, **kwargs)
        self.token = openapi_key

    async def get_token(self):
        return self.token
