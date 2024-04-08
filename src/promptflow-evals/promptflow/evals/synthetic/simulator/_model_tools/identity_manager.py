# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import asyncio
import logging
import os
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional
from urllib.parse import urlparse

from azure.identity import AzureCliCredential, ManagedIdentityCredential
from azure.keyvault.secrets import SecretClient
from msal import ConfidentialClientApplication

http_logger = logging.getLogger("azure.core.pipeline.policies.http_logging_policy")

AZURE_TOKEN_REFRESH_INTERVAL = 600  # seconds


class TokenScope(Enum):
    AZURE_ENDPOINT = "https://ml.azure.com"
    AZURE_OPENAI_API = "https://cognitiveservices.azure.com"


def build_token_manager(
    authorization_type: str,
    endpoint_type: str,
    keyvault: Optional[str] = None,
    keyvault_secret_identifier: Optional[str] = None,
    logger: logging.Logger = logging.getLogger("TokenManager"),
):
    authorization_header = "Bearer"

    # Define authorization token manager
    if authorization_type == "key_vault_secret":
        if endpoint_type != "openai_api":
            authorization_header = "api-key"
        return KeyVaultAPITokenManager(
            secret_identifier=keyvault_secret_identifier,
            auth_header=authorization_header,
            logger=logger,
        )
    if authorization_type == "managed_identity":
        if endpoint_type == "azure_endpoint":
            token_scope = TokenScope.AZURE_ENDPOINT
        elif endpoint_type == "azure_openai_api":
            token_scope = TokenScope.AZURE_OPENAI_API
        else:
            raise ValueError(f"Unknown endpoint_type: {endpoint_type}")
        return ManagedIdentityAPITokenManager(
            token_scope=token_scope,
            auth_header=authorization_header,
            logger=logger,
        )
    if authorization_type == "compliant":
        return CompliantTokenManager(
            keyvault=keyvault,
            auth_header=authorization_header,
            logger=logger,
        )
    raise ValueError(f"Unknown authorization_type: {authorization_type}")


class APITokenManager(ABC):
    def __init__(self, logger, auth_header="Bearer"):
        self.logger = logger
        self.auth_header = auth_header
        self.lock = asyncio.Lock()
        self.credential = self.get_aad_credential()
        self.token = None
        self.last_refresh_time = None

    def get_aad_credential(self):
        identity_client_id = os.environ.get("DEFAULT_IDENTITY_CLIENT_ID", None)
        if identity_client_id is not None:
            self.logger.info(f"Using DEFAULT_IDENTITY_CLIENT_ID: {identity_client_id}")
            credential = ManagedIdentityCredential(client_id=identity_client_id)
        else:
            # Good for local testing.
            self.logger.info("Environment variable DEFAULT_IDENTITY_CLIENT_ID is not set, using DefaultAzureCredential")
            credential = AzureCliCredential()
        return credential

    @abstractmethod
    async def get_token(self):
        pass


class ManagedIdentityAPITokenManager(APITokenManager):
    def __init__(self, token_scope, logger, **kwargs):
        super().__init__(logger, **kwargs)
        self.token_scope = token_scope

    async def get_token(self):
        async with self.lock:  # prevent multiple threads from refreshing the token at the same time
            if (
                self.token is None
                or self.last_refresh_time is None
                or time.time() - self.last_refresh_time > AZURE_TOKEN_REFRESH_INTERVAL
            ):
                self.last_refresh_time = time.time()
                self.token = self.credential.get_token(self.token_scope.value).token
                self.logger.info("Refreshed Azure endpoint token.")

        return self.token


class KeyVaultAPITokenManager(APITokenManager):
    def __init__(self, secret_identifier, logger, **kwargs):
        super().__init__(logger, **kwargs)

        # Parse secret identifier to get Key Vault URL and secret name
        parsed_uri = urlparse(secret_identifier)
        keyvault_url = "{uri.scheme}://{uri.netloc}/".format(uri=parsed_uri)
        secret_name = parsed_uri.path.split("/")[2]

        # Get Open AI API key from Key Vault and set it
        secret_client = SecretClient(vault_url=keyvault_url, credential=self.credential)
        openai_api_secret = secret_client.get_secret(secret_name)
        logger.info(f"Retrieved API key: {openai_api_secret.name} from Azure Key Vault")

        self.token = openai_api_secret.value

    async def get_token(self):
        return self.token


class CompliantTokenManager(APITokenManager):
    def __init__(self, keyvault, logger, **kwargs):
        super().__init__(logger, **kwargs)
        client_id = keyvault.get_secret(name="approvalClientId")
        client_secret = keyvault.get_secret(name="approvalClientSecret")
        tenant_id = keyvault.get_secret(name="approvalTenantId")
        self.resource = keyvault.get_secret(name="approvalResource")

        self.app = ConfidentialClientApplication(
            client_id=client_id,
            authority="https://login.microsoftonline.com/" + tenant_id,
            client_credential=client_secret,
        )

    async def get_token(self):
        result = self.app.acquire_token_for_client(scopes=[self.resource + "/.default"])
        return result["access_token"]
