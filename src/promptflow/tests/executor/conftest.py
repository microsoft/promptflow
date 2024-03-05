import pytest
from fastapi.testclient import TestClient

from promptflow._core.openai_injector import inject_openai_api
from promptflow.executor._service.app import app


@pytest.fixture(autouse=True, scope="session")
def inject_api_executor():
    """Inject OpenAI API during test session.

    AOAI call in promptflow should involve trace logging and header injection. Inject
    function to API call in test scenario."""
    inject_openai_api()


@pytest.fixture(autouse=True, scope="session")
def executor_client():
    """Executor client for testing."""
    # Set raise_server_exceptions to False to avoid raising exceptions
    # from the server and return them as error response.
    yield TestClient(app, raise_server_exceptions=False)
