import json
import os
import shutil
import sys
from pathlib import Path
from tempfile import mkdtemp

import pytest
import yaml
from azure.ai.ml import MLClient
from azure.identity import AzureCliCredential

PROMOTFLOW_ROOT = Path(__file__) / "../../.."
CONNECTION_FILE = (PROMOTFLOW_ROOT / "connections.json").resolve().absolute().as_posix()
root_str = str(PROMOTFLOW_ROOT.resolve().absolute())
if root_str not in sys.path:
    sys.path.insert(0, root_str)

from pytest_mock import MockerFixture  # noqa: E402

from promptflow._constants import PROMPTFLOW_CONNECTIONS, STORAGE_ACCOUNT_NAME, AzureMLConfig  # noqa: E402
from promptflow.core import RunTracker  # noqa: E402
from promptflow.core.cache_manager import CacheManager  # noqa: E402
from promptflow.core.tools_manager import BuiltinsManager  # noqa: E402
from promptflow.executor import FlowExecutionCoodinator  # noqa: E402
from promptflow.storage.cache_storage import LocalCacheStorage  # noqa: E402
from promptflow.storage.local_run_storage import LocalRunStorage  # noqa: E402

PROMOTFLOW_ROOT = Path(__file__).absolute().parents[2]


@pytest.fixture
def basic_executor() -> FlowExecutionCoodinator:
    dummy_run_dir = (PROMOTFLOW_ROOT / "tests/test_configs/dummy_runs").absolute().resolve().as_posix()
    tmpdir = mkdtemp()
    shutil.copytree(dummy_run_dir, tmpdir, dirs_exist_ok=True)
    os.environ["PROMPTFLOW_DUMMY_RUN_DIR"] = tmpdir
    coodinator = FlowExecutionCoodinator.init_from_env()
    coodinator._nthreads = 4  # Reduce the number of threads to avoid rate limit
    return coodinator


@pytest.fixture
def local_executor() -> FlowExecutionCoodinator:
    builtins_manager = BuiltinsManager()
    local_run_storage = LocalRunStorage(
        db_folder_path=str(Path(mkdtemp()) / ".test_db"),
        db_name="test.db",
    )
    local_cache_storage = LocalCacheStorage(
        db_folder_path=str(Path(mkdtemp()) / ".test_db"),
        db_name="test.db",
    )
    cache_manager = CacheManager(local_run_storage, local_cache_storage)
    run_tracker = RunTracker(local_run_storage)
    return FlowExecutionCoodinator(
        builtins_manager,
        cache_manager,
        run_tracker,
        nthreads=4,
    )


@pytest.fixture
def use_secrets_config_file(mocker: MockerFixture):
    mocker.patch.dict(os.environ, {PROMPTFLOW_CONNECTIONS: CONNECTION_FILE})


@pytest.fixture(scope="session")
def deployment_model_config():
    prompt_ci_yaml = Path(PROMOTFLOW_ROOT / "../../deploy/model/promptflow-eastus.yaml").resolve().absolute()
    if not prompt_ci_yaml.exists():
        raise FileNotFoundError(
            f"Missing {str(prompt_ci_yaml)!r}, please update the file path if it's moved elsewhere."
        )

    with open(prompt_ci_yaml, "r") as f:
        deploy_config = yaml.safe_load(f)
    return deploy_config


@pytest.fixture
def set_azureml_config(mocker: MockerFixture, deployment_model_config):
    azure_ml_config = {
        AzureMLConfig.SUBSCRIPTION_ID: deployment_model_config["deployment"]["subscription_id"],
        AzureMLConfig.RESOURCE_GROUP_NAME: deployment_model_config["deployment"]["resource_group"],
        AzureMLConfig.WORKSPACE_NAME: deployment_model_config["deployment"]["workspace_name"],
        AzureMLConfig.MT_ENDPOINT: deployment_model_config["deployment"]["mt_service_endpoint"],
        STORAGE_ACCOUNT_NAME: deployment_model_config["storage"]["storage_account"],
    }
    mocker.patch.dict(os.environ, azure_ml_config)


@pytest.fixture
def example_prompt_template() -> str:
    with open(PROMOTFLOW_ROOT / "tests/test_configs/prompt_templates/marketing_writer/prompt.jinja2") as f:
        prompt_template = f.read()
    return prompt_template


@pytest.fixture
def chat_history() -> list:
    with open(PROMOTFLOW_ROOT / "tests/test_configs/prompt_templates/marketing_writer/history.json") as f:
        history = json.load(f)
    return history


@pytest.fixture(scope="session")
def ml_client(deployment_model_config) -> MLClient:
    deployment = deployment_model_config["deployment"]
    return MLClient(
        credential=AzureCliCredential(),
        subscription_id=deployment["subscription_id"],
        resource_group_name=deployment["resource_group"],
        workspace_name=deployment["workspace_name"],
    )
