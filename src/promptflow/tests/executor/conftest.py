import pytest


@pytest.fixture(autouse=True, scope="session")
def inject_api_executor(inject_api):
    """Inject OpenAI API during test session.

    AOAI call in promptflow should involve trace logging and header injection. Inject
    function to API call in test scenario."""
    pass
