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

    yield TestClient(app)
