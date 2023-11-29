import importlib
import json
import os
import tempfile
from multiprocessing import Lock
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from _constants import (
    CONNECTION_FILE,
    DEFAULT_REGISTRY_NAME,
    DEFAULT_RESOURCE_GROUP_NAME,
    DEFAULT_RUNTIME_NAME,
    DEFAULT_SUBSCRIPTION_ID,
    DEFAULT_WORKSPACE_NAME,
    ENV_FILE,
    CLI_PERF_MONITOR_AGENT,
)
from _pytest.monkeypatch import MonkeyPatch
from dotenv import load_dotenv
from filelock import FileLock
from pytest_mock import MockerFixture
from sdk_cli_azure_test.recording_utilities import SanitizedValues, is_replay

from promptflow._cli._utils import AzureMLWorkspaceTriad
from promptflow._constants import PROMPTFLOW_CONNECTIONS
from promptflow._core.connection_manager import ConnectionManager
from promptflow._core.openai_injector import inject_openai_api
from promptflow._utils.context_utils import _change_working_dir
from promptflow.connections import AzureOpenAIConnection

load_dotenv()


@pytest.fixture(scope="session", autouse=True)
def modify_work_directory():
    os.chdir(Path(__file__).parent.parent.absolute())


@pytest.fixture(autouse=True, scope="session")
def mock_build_info():
    """Mock BUILD_INFO environment variable in pytest.

    BUILD_INFO is set as environment variable in docker image, but not in local test.
    So we need to mock it in test senario. Rule - build_number is set as
    ci-<BUILD_BUILDNUMBER> in CI pipeline, and set as local in local dev test."""
    if "BUILD_INFO" not in os.environ:
        m = MonkeyPatch()
        build_number = os.environ.get("BUILD_BUILDNUMBER", "")
        buid_info = {"build_number": f"ci-{build_number}" if build_number else "local-pytest"}
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
def prepare_symbolic_flow() -> str:
    flows_dir = Path(__file__).parent / "test_configs" / "flows"
    target_folder = flows_dir / "web_classification_with_symbolic"
    source_folder = flows_dir / "web_classification"

    with _change_working_dir(target_folder):

        for file_name in os.listdir(source_folder):
            if not Path(file_name).exists():
                os.symlink(source_folder / file_name, file_name)
    return target_folder


@pytest.fixture(scope="session")
def install_custom_tool_pkg():
    # The tests could be running in parallel. Use a lock to prevent race conditions.
    lock = FileLock("custom_tool_pkg_installation.lock")
    with lock:
        try:
            import my_tool_package  # noqa: F401

        except ImportError:
            import subprocess
            import sys

            subprocess.check_call([sys.executable, "-m", "pip", "install", "test-custom-tools==0.0.2"])


@pytest.fixture
def mocked_ws_triple() -> AzureMLWorkspaceTriad:
    return AzureMLWorkspaceTriad("mock_subscription_id", "mock_resource_group", "mock_workspace_name")


@pytest.fixture(scope="session")
def mock_list_func():
    """Mock function object for dynamic list testing."""

    def my_list_func(prefix: str = "", size: int = 10, **kwargs):
        return [
            {
                "value": "fig0",
                "display_value": "My_fig0",
                "hyperlink": "https://www.bing.com/search?q=fig0",
                "description": "this is 0 item",
            },
            {
                "value": "kiwi1",
                "display_value": "My_kiwi1",
                "hyperlink": "https://www.bing.com/search?q=kiwi1",
                "description": "this is 1 item",
            },
        ]

    return my_list_func


@pytest.fixture(scope="session")
def mock_module_with_list_func(mock_list_func):
    """Mock module object for dynamic list testing."""
    mock_module = MagicMock()
    mock_module.my_list_func = mock_list_func
    mock_module.my_field = 1
    original_import_module = importlib.import_module  # Save this to prevent recursion

    with patch.object(importlib, "import_module") as mock_import:

        def side_effect(module_name, *args, **kwargs):
            if module_name == "my_tool_package.tools.tool_with_dynamic_list_input":
                return mock_module
            else:
                return original_import_module(module_name, *args, **kwargs)

        mock_import.side_effect = side_effect
        yield


# below fixtures are used for pfazure and global config tests
@pytest.fixture
def subscription_id() -> str:
    if is_replay():
        return SanitizedValues.SUBSCRIPTION_ID
    else:
        return os.getenv("PROMPT_FLOW_SUBSCRIPTION_ID", DEFAULT_SUBSCRIPTION_ID)


@pytest.fixture
def resource_group_name() -> str:
    if is_replay():
        return SanitizedValues.RESOURCE_GROUP_NAME
    else:
        return os.getenv("PROMPT_FLOW_RESOURCE_GROUP_NAME", DEFAULT_RESOURCE_GROUP_NAME)


@pytest.fixture
def workspace_name() -> str:
    if is_replay():
        return SanitizedValues.WORKSPACE_NAME
    else:
        return os.getenv("PROMPT_FLOW_WORKSPACE_NAME", DEFAULT_WORKSPACE_NAME)


@pytest.fixture
def runtime_name() -> str:
    return os.getenv("PROMPT_FLOW_RUNTIME_NAME", DEFAULT_RUNTIME_NAME)


@pytest.fixture
def registry_name() -> str:
    return os.getenv("PROMPT_FLOW_REGISTRY_NAME", DEFAULT_REGISTRY_NAME)


@pytest.fixture
def cli_perf_monitor_agent() -> str:
    return CLI_PERF_MONITOR_AGENT
