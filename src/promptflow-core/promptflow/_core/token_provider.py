import threading
from abc import ABC, abstractmethod
from promptflow.exceptions import UserErrorException
from promptflow._utils.credential_utils import get_default_azure_credential


# to access azure ai services, we need to get the token with this scope
COGNITIVE_SCOPE = "https://cognitiveservices.azure.com/.default"


class TokenProviderABC(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    def get_token(self) -> str:
        pass


class StaticTokenProvider(TokenProviderABC):
    def __init__(self, token: str) -> None:
        super().__init__()
        self.token = token

    def get_token(self) -> str:
        return self.token


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
        try:
            # Initialize a credential instance
            self.credential = get_default_azure_credential()
        except ImportError as ex:
            raise UserErrorException(
                "Failed to initialize AzureTokenProvider. "
                + f"Please try 'pip install azure.identity' to install dependency, {ex.msg}."
            )

    def get_token(self):
        scope = COGNITIVE_SCOPE
        return self.credential.get_token(scope).token
