import importlib
import json
import os
import platform
import tempfile
from multiprocessing import Lock
from pathlib import Path
from typing import TypedDict
from unittest.mock import MagicMock, patch

import pytest
import requests
from _constants import (
    CONNECTION_FILE,
    DEFAULT_RESOURCE_GROUP_NAME,
    DEFAULT_SUBSCRIPTION_ID,
    DEFAULT_WORKSPACE_NAME,
    ENV_FILE,
    PROMPTFLOW_ROOT,
)
from _pytest.monkeypatch import MonkeyPatch
from dotenv import load_dotenv
from filelock import FileLock
from mock import mock
from pytest_mock import MockerFixture

from promptflow._constants import PROMPTFLOW_CONNECTIONS
from promptflow._core.connection_manager import ConnectionManager
from promptflow._sdk.entities._connection import AzureOpenAIConnection
from promptflow._utils.context_utils import _change_working_dir

try:
    from promptflow.recording.local import invoke_prompt_flow_service
    from promptflow.recording.record_mode import is_replay
except ImportError:
    # Run test in empty mode if promptflow-recording is not installed
    def is_replay():
        return False

    # copy lines from /src/promptflow-recording/promptflow/recording/local/test_utils.py
    import time

    from promptflow._cli._pf._service import _start_background_service_on_unix, _start_background_service_on_windows
    from promptflow._sdk._service.utils.utils import get_pfs_host, get_pfs_host_after_check_wildcard, get_pfs_port

    def invoke_prompt_flow_service():
        service_host = get_pfs_host()
        host = get_pfs_host_after_check_wildcard(service_host)
        port = str(get_pfs_port(host))
        if platform.system() == "Windows":
            _start_background_service_on_windows(port, service_host)
        else:
            _start_background_service_on_unix(port, service_host)
        time.sleep(20)
        response = requests.get(f"http://{host}:{port}/heartbeat")
        assert response.status_code == 200, "prompt flow service is not healthy via /heartbeat"
        return port, host


load_dotenv()


def pytest_configure():
    pytest.is_replay = is_replay()


@pytest.fixture(scope="session", autouse=True)
def modify_work_directory():
    os.chdir(PROMPTFLOW_ROOT)


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
    flows_dir = PROMPTFLOW_ROOT / "tests" / "test_configs" / "flows"
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


@pytest.fixture(scope="session")
def mock_generated_by_func():
    """Mock function object for generated_by testing."""

    def my_generated_by_func(index_type: str):
        inputs = ""
        if index_type == "Azure Cognitive Search":
            inputs = {"index_type": index_type, "index": "index_1"}
        elif index_type == "Workspace MLIndex":
            inputs = {"index_type": index_type, "index": "index_2"}

        result = json.dumps(inputs)
        return result

    return my_generated_by_func


@pytest.fixture(scope="session")
def mock_reverse_generated_by_func():
    """Mock function object for reverse_generated_by testing."""

    def my_reverse_generated_by_func(index_json: str):
        result = json.loads(index_json)
        return result

    return my_reverse_generated_by_func


@pytest.fixture
def enable_logger_propagate():
    """This is for test cases that need to check the log output."""
    from promptflow._utils.logger_utils import get_cli_sdk_logger

    logger = get_cli_sdk_logger()
    original_value = logger.propagate
    logger.propagate = True
    yield
    logger.propagate = original_value


@pytest.fixture(scope="session")
def mock_module_with_for_retrieve_tool_func_result(
    mock_list_func, mock_generated_by_func, mock_reverse_generated_by_func
):
    """Mock module object for dynamic list testing."""
    mock_module_list_func = MagicMock()
    mock_module_list_func.my_list_func = mock_list_func
    mock_module_list_func.my_field = 1
    mock_module_generated_by = MagicMock()
    mock_module_generated_by.generated_by_func = mock_generated_by_func
    mock_module_generated_by.reverse_generated_by_func = mock_reverse_generated_by_func
    mock_module_generated_by.my_field = 1
    original_import_module = importlib.import_module  # Save this to prevent recursion

    with patch.object(importlib, "import_module") as mock_import:

        def side_effect(module_name, *args, **kwargs):
            if module_name == "my_tool_package.tools.tool_with_dynamic_list_input":
                return mock_module_list_func
            elif module_name == "my_tool_package.tools.tool_with_generated_by_input":
                return mock_module_generated_by
            else:
                return original_import_module(module_name, *args, **kwargs)

        mock_import.side_effect = side_effect
        yield


# region pfazure constants
@pytest.fixture
def subscription_id() -> str:
    return os.getenv("PROMPT_FLOW_SUBSCRIPTION_ID", DEFAULT_SUBSCRIPTION_ID)


@pytest.fixture
def resource_group_name() -> str:
    return os.getenv("PROMPT_FLOW_RESOURCE_GROUP_NAME", DEFAULT_RESOURCE_GROUP_NAME)


@pytest.fixture
def workspace_name() -> str:
    return os.getenv("PROMPT_FLOW_WORKSPACE_NAME", DEFAULT_WORKSPACE_NAME)


@pytest.fixture
def reset_tracer_provider():
    """Force reset tracer provider."""
    with patch("opentelemetry.trace._TRACER_PROVIDER", None), patch(
        "opentelemetry.trace._TRACER_PROVIDER_SET_ONCE._done", False
    ):
        yield


class CSharpProject(TypedDict):
    flow_dir: str
    data: str
    init: str


def construct_csharp_test_project(flow_name: str) -> CSharpProject:
    root_of_test_cases = os.getenv("CSHARP_TEST_PROJECTS_ROOT", None)
    if not root_of_test_cases:
        pytest.skip(reason="No C# test cases found, please set CSHARP_TEST_CASES_ROOT.")
    root_of_test_cases = Path(root_of_test_cases)
    return {
        "flow_dir": (root_of_test_cases / flow_name / "bin" / "Debug" / "net6.0").as_posix(),
        "data": (root_of_test_cases / flow_name / "data.jsonl").as_posix(),
        "init": (root_of_test_cases / flow_name / "init.json").as_posix(),
    }


@pytest.fixture
def csharp_test_project_basic() -> CSharpProject:
    return construct_csharp_test_project("Basic")


@pytest.fixture
def csharp_test_project_basic_chat() -> CSharpProject:
    return construct_csharp_test_project("BasicChat")


@pytest.fixture
def csharp_test_project_function_mode_basic() -> CSharpProject:
    return construct_csharp_test_project("FunctionModeBasic")


@pytest.fixture
def csharp_test_project_class_init_flex_flow() -> CSharpProject:
    is_in_ci_pipeline = os.getenv("IS_IN_CI_PIPELINE", "false").lower() == "true"
    if is_in_ci_pipeline:
        pytest.skip(reason="need to avoid fetching connection from local pfs to enable this in ci")
    return construct_csharp_test_project("ClassInitFlexFlow")


@pytest.fixture(scope="session")
def otlp_collector():
    """A session scope fixture, a separate standby prompt flow service serves as OTLP collector."""
    port, service_host = invoke_prompt_flow_service()
    # mock invoke prompt flow service as it has been invoked already
    with mock.patch("promptflow._sdk._tracing._invoke_pf_svc", return_value=(port, service_host)), mock.patch(
        "promptflow._sdk._tracing.is_pfs_service_healthy", return_value=True
    ):
        yield
