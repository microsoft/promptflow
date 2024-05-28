import json
import multiprocessing
import os
from pathlib import Path
from typing import Dict
from unittest.mock import patch

import pytest
from azure.identity import DefaultAzureCredential
from pytest_mock import MockerFixture

from promptflow.azure import PFClient as AzurePFClient
from promptflow.client import PFClient
from promptflow.core import AzureOpenAIModelConfiguration
from promptflow.executor._line_execution_process_pool import _process_wrapper
from promptflow.executor._process_manager import create_spawned_fork_process_manager
from promptflow.tracing._integrations._openai_injector import inject_openai_api

try:
    from promptflow.recording.local import recording_array_reset
    from promptflow.recording.record_mode import is_in_ci_pipeline, is_live, is_record, is_replay
except ImportError as e:
    print(f"Failed to import promptflow-recording: {e}")

    # Run test in empty mode if promptflow-recording is not installed
    def recording_array_reset():
        pass

    def is_in_ci_pipeline():
        return False

    def is_live():
        return False

    def is_record():
        return False

    def is_replay():
        return False


PROMPTFLOW_ROOT = Path(__file__) / "../../../.."
CONNECTION_FILE = (PROMPTFLOW_ROOT / "promptflow-evals/connections.json").resolve().absolute().as_posix()
RECORDINGS_TEST_CONFIGS_ROOT = Path(PROMPTFLOW_ROOT / "promptflow-evals/tests/recordings/local").resolve()


@pytest.fixture
def configure_default_azure_credential():
    if os.path.exists(CONNECTION_FILE):
        with open(file=CONNECTION_FILE, mode="r") as f:
            dev_connections = json.load(f)

        # for running e2e test which uses DefaultAzureCredential in ci pipeline
        if "pf-evals-sp" in dev_connections:
            creds = dev_connections["pf-evals-sp"]["value"]
            for key, value in creds.items():
                os.environ[key] = value


def pytest_configure():
    pytest.is_live = is_live()
    pytest.is_record = is_record()
    pytest.is_replay = is_replay()
    pytest.is_in_ci_pipeline = is_in_ci_pipeline()

    print()
    print(f"pytest.is_live: {pytest.is_live}")
    print(f"pytest.is_record: {pytest.is_record}")
    print(f"pytest.is_replay: {pytest.is_replay}")
    print(f"pytest.is_in_ci_pipeline: {pytest.is_in_ci_pipeline}")


@pytest.fixture
def mock_model_config() -> dict:
    return AzureOpenAIModelConfiguration(
        azure_endpoint="aoai-api-endpoint",
        api_key="aoai-api-key",
        api_version="2023-07-01-preview",
        azure_deployment="aoai-deployment",
    )


@pytest.fixture
def mock_project_scope() -> dict:
    return {
        "subscription_id": "subscription-id",
        "resource_group_name": "resource-group-name",
        "project_name": "project-name",
    }


@pytest.fixture
def model_config() -> dict:
    conn_name = "azure_openai_model_config"

    with open(
        file=CONNECTION_FILE,
        mode="r",
    ) as f:
        dev_connections = json.load(f)

    if conn_name not in dev_connections:
        raise ValueError(f"Connection '{conn_name}' not found in dev connections.")

    model_config = AzureOpenAIModelConfiguration(**dev_connections[conn_name]["value"])

    AzureOpenAIModelConfiguration.__repr__ = lambda self: "<sensitive data redacted>"

    return model_config


@pytest.fixture
def project_scope() -> dict:
    conn_name = "azure_ai_project_scope"

    with open(
        file=CONNECTION_FILE,
        mode="r",
    ) as f:
        dev_connections = json.load(f)

    if conn_name not in dev_connections:
        raise ValueError(f"Connection '{conn_name}' not found in dev connections.")

    return dev_connections[conn_name]["value"]


@pytest.fixture
def mock_trace_destination_to_cloud(project_scope: dict):
    """Mock trace destination to cloud."""

    subscription_id = project_scope["subscription_id"]
    resource_group_name = project_scope["resource_group_name"]
    workspace_name = project_scope["project_name"]

    trace_destination = (
        f"azureml://subscriptions/{subscription_id}/resourceGroups/{resource_group_name}/"
        f"providers/Microsoft.MachineLearningServices/workspaces/{workspace_name}"
    )
    with patch("promptflow._sdk._configuration.Configuration.get_trace_destination", return_value=trace_destination):
        yield


@pytest.fixture
def azure_pf_client(project_scope: Dict):
    """The fixture, returning AzurePFClient"""
    return AzurePFClient(
        subscription_id=project_scope["subscription_id"],
        resource_group_name=project_scope["resource_group_name"],
        workspace_name=project_scope["project_name"],
        credential=DefaultAzureCredential(),
    )


@pytest.fixture
def pf_client() -> PFClient:
    """The fixture, returning PRClient"""
    return PFClient()


# ==================== Recording injection ====================
# To inject patches in subprocesses, add new mock method in setup_recording_injection_if_enabled
# in fork mode, this is automatically enabled.
# in spawn mode, we need to declare recording in each process separately.

SpawnProcess = multiprocessing.get_context("spawn").Process


class MockSpawnProcess(SpawnProcess):
    def __init__(self, group=None, target=None, *args, **kwargs):
        if target == _process_wrapper:
            target = _mock_process_wrapper
        if target == create_spawned_fork_process_manager:
            target = _mock_create_spawned_fork_process_manager
        super().__init__(group, target, *args, **kwargs)


@pytest.fixture
def recording_injection(mocker: MockerFixture):
    original_process_class = multiprocessing.get_context("spawn").Process
    multiprocessing.get_context("spawn").Process = MockSpawnProcess
    if "spawn" == multiprocessing.get_start_method():
        multiprocessing.Process = MockSpawnProcess

    patches = setup_recording_injection_if_enabled()

    try:
        yield
    finally:
        if pytest.is_replay or pytest.is_record:
            from promptflow.recording.local import RecordStorage

            RecordStorage.get_instance().delete_lock_file()
        if pytest.is_live:
            from promptflow.recording.local import delete_count_lock_file

            delete_count_lock_file()
        recording_array_reset()

        multiprocessing.get_context("spawn").Process = original_process_class
        if "spawn" == multiprocessing.get_start_method():
            multiprocessing.Process = original_process_class

        for patcher in patches:
            patcher.stop()


def setup_recording_injection_if_enabled():
    patches = []

    def start_patches(patch_targets):
        for target, mock_func in patch_targets.items():
            patcher = patch(target, mock_func)
            patches.append(patcher)
            patcher.start()

    if is_replay() or is_record():
        from promptflow.recording.local import RecordStorage, inject_async_with_recording, inject_sync_with_recording
        from promptflow.recording.record_mode import check_pydantic_v2

        check_pydantic_v2()
        file_path = RECORDINGS_TEST_CONFIGS_ROOT / "evals.node_cache.shelve"
        RecordStorage.get_instance(file_path)

        patch_targets = {
            "promptflow.tracing._integrations._openai_injector.inject_sync": inject_sync_with_recording,
            "promptflow.tracing._integrations._openai_injector.inject_async": inject_async_with_recording,
        }
        start_patches(patch_targets)

    if is_live() and is_in_ci_pipeline():
        from promptflow.recording.local import inject_async_with_recording, inject_sync_with_recording

        patch_targets = {
            "promptflow.tracing._integrations._openai_injector.inject_sync": inject_sync_with_recording,
            "promptflow.tracing._integrations._openai_injector.inject_async": inject_async_with_recording,
        }
        start_patches(patch_targets)

    inject_openai_api()
    return patches


def _mock_process_wrapper(*args, **kwargs):
    setup_recording_injection_if_enabled()
    return _process_wrapper(*args, **kwargs)


def _mock_create_spawned_fork_process_manager(*args, **kwargs):
    setup_recording_injection_if_enabled()
    return create_spawned_fork_process_manager(*args, **kwargs)
