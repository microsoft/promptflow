import threading
import time

from abc import ABC, abstractmethod
from azure.identity import DefaultAzureCredential
from datetime import datetime, timedelta

COGNITIVE_AUDIENCE = "https://cognitiveservices.azure.com/"


class TokenProviderABC(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    def get_token(self) -> str:
        pass


class AzureTokenProvider(TokenProviderABC):
    _instance_lock = threading.Lock()
    _instance = None

    def __new__(cls, *args, **kwargs):
        with cls._instance_lock:
            if not cls._instance:
                cls._instance = super().__new__(cls)
                cls._instance._init_instance()
            return cls._instance

    def _init_instance(self):
        # Initialize a dictionary to store caches for different audiences
        self.audience_tokens = {}
        # Initialize a dictionary to store expiry times for different audiences
        self.audience_expiry_times = {}
        self._token_lock = threading.Lock()

    def get_token(self, audience=COGNITIVE_AUDIENCE):
        with self._token_lock:
            cached_token = self.audience_tokens.get(audience, None)
            expiry_time = self.audience_expiry_times.get(audience, None)

        # Check if there is a cached token and it's not expired
        if cached_token and expiry_time and datetime.now() < expiry_time:
            return cached_token

        # If no cached token or it's expired, refresh the token
        new_token, expiry_time = self.refresh_token(audience)

        # Update the cache
        with self._token_lock:
            self.audience_tokens[audience] = new_token
            self.audience_expiry_times[audience] = expiry_time

        return new_token

    def refresh_token(self, audience):
        # Use Azure identity library to obtain a new token
        credential = DefaultAzureCredential()
        token = credential.get_token(audience)

        # Set the expiry time for the new token
        expiry_time = datetime.now() + timedelta(seconds=token.expires_on - time.time())

        return token.token, expiry_time
