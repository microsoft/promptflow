import json
import os
import tempfile
from multiprocessing import Lock
from pathlib import Path

import pytest
from _constants import CONNECTION_FILE, ENV_FILE
from _pytest.monkeypatch import MonkeyPatch
from pytest_mock import MockerFixture

from promptflow._constants import PROMPTFLOW_CONNECTIONS
from promptflow._core.connection_manager import ConnectionManager
from promptflow._core.openai_injector import inject_openai_api
from promptflow._utils.context_utils import _change_working_dir
from promptflow.connections import AzureOpenAIConnection


@pytest.fixture(autouse=True, scope="session")
def mock_build_info():
    """Mock BUILD_INFO environment variable in pytest.

    BUILD_INFO is set as environment variable in docker image, but not in local test.
    So we need to mock it in test senario. Rule - build_number is set as
    ci-<BUILD_BUILDNUMBER> in CI pipeline, and set as local in local dev test."""
    if "BUILD_INFO" not in os.environ:
        m = MonkeyPatch()
        build_number = os.environ.get("BUILD_BUILDNUMBER", "")
        buid_info = {
            "build_number": f"ci-{build_number}" if build_number else "local-pytest"
        }
        m.setenv("BUILD_INFO", json.dumps(buid_info))
        yield m


@pytest.fixture(autouse=True, scope="session")
def inject_api():
    """Inject OpenAI API during test session.

    AOAI call in promptflow should involve trace logging and header injection. Inject
    function to API call in test scenario."""
    inject_openai_api()


@pytest.fixture
def dev_connections() -> dict:
    with open(CONNECTION_FILE, "r") as f:
        return json.load(f)


@pytest.fixture
def use_secrets_config_file(mocker: MockerFixture):
    mocker.patch.dict(os.environ, {PROMPTFLOW_CONNECTIONS: CONNECTION_FILE})


@pytest.fixture
def env_with_secrets_config_file():
    _lock = Lock()
    with _lock:
        with open(ENV_FILE, "w") as f:
            f.write(f"{PROMPTFLOW_CONNECTIONS}={CONNECTION_FILE}\n")
        yield ENV_FILE
        if os.path.exists(ENV_FILE):
            os.remove(ENV_FILE)


@pytest.fixture
def azure_open_ai_connection() -> AzureOpenAIConnection:
    return ConnectionManager().get("azure_open_ai_connection")


@pytest.fixture
def temp_output_dir() -> str:
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def default_subscription_id() -> str:
    return "96aede12-2f73-41cb-b983-6d11a904839b"


@pytest.fixture
def default_resource_group() -> str:
    return "promptflow"


@pytest.fixture
def default_workspace() -> str:
    return "promptflow-eastus"


@pytest.fixture
def workspace_with_acr_access() -> str:
    return "promptflow-eastus-dev"


@pytest.fixture
def prepare_symbolic_flow() -> str:
    flows_dir = Path(__file__).parent / "test_configs" / "flows"
    target_folder = flows_dir / "web_classification_with_symbolic"
    source_folder = flows_dir / "web_classification"

    with _change_working_dir(target_folder):
        for file_name in os.listdir(source_folder):
            if not Path(file_name).exists():
                os.symlink(source_folder / file_name, file_name)
    return target_folder
