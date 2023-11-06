import threading

from abc import ABC, abstractmethod
from azure.identity import DefaultAzureCredential

# to access azure ai services, we need to get the token with this audience
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
        # Initialize a credential instance
        self.credential = DefaultAzureCredential()

    def get_token(self, audience=COGNITIVE_AUDIENCE):
        return self.credential.get_token(audience).token
