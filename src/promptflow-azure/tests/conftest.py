import json
import os
import tempfile
from pathlib import Path

import pytest
from _constants import CONNECTION_FILE, PROMPTFLOW_ROOT
from _pytest.monkeypatch import MonkeyPatch
from dotenv import load_dotenv
from pytest_mock import MockerFixture

from promptflow._constants import PROMPTFLOW_CONNECTIONS
from promptflow._core.connection_manager import ConnectionManager
from promptflow._sdk._pf_client import PFClient as LocalClient
from promptflow._sdk.entities._connection import AzureOpenAIConnection, _Connection
from promptflow._utils.context_utils import _change_working_dir

load_dotenv()
_connection_setup = False


@pytest.fixture(autouse=True)
def declare_test_package(monkeypatch: MonkeyPatch):
    monkeypatch.setenv("PROMPT_FLOW_TEST_PACKAGE", "promptflow-azure")


@pytest.fixture
def local_client() -> LocalClient:
    yield LocalClient()


@pytest.fixture
def setup_local_connection(local_client, azure_open_ai_connection):
    global _connection_setup
    if _connection_setup:
        return
    connection_dict = json.loads(open(CONNECTION_FILE, "r").read())
    for name, _dct in connection_dict.items():
        if _dct["type"] == "BingConnection":
            continue
        local_client.connections.create_or_update(_Connection._from_execution_connection_dict(name=name, data=_dct))
    _connection_setup = True


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
def use_secrets_config_file(mocker: MockerFixture):
    mocker.patch.dict(os.environ, {PROMPTFLOW_CONNECTIONS: CONNECTION_FILE})


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


@pytest.fixture
def enable_logger_propagate():
    """This is for test cases that need to check the log output."""
    from promptflow._utils.logger_utils import get_cli_sdk_logger

    logger = get_cli_sdk_logger()
    original_value = logger.propagate
    logger.propagate = True
    yield
    logger.propagate = original_value
