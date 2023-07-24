import io
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from omegaconf import OmegaConf
from pytest_mock import MockFixture

from promptflow._constants import ComputeType, PromptflowEdition
from promptflow.exceptions import UserAuthenticationError, UserErrorException
from promptflow.runtime.constants import DEFAULT_CONFIGS
from promptflow.runtime.error_codes import ConfigFileNotExists
from promptflow.runtime.runtime_config import RuntimeConfig, load_runtime_config
from promptflow.runtime.utils import get_logger, get_workspace_config
from promptflow.runtime.utils._mlclient_helper import get_mlclient_from_env

from .._azure_utils import get_cred
from ..conftest import RUNTIME_TEST_CONFIGS_ROOT

test_logger = get_logger(__name__)


@pytest.fixture
def runtime_config():
    file_path = Path(RUNTIME_TEST_CONFIGS_ROOT / "configs/test_config.yaml").resolve().absolute()
    return load_runtime_config(file_path)


@pytest.mark.unittest
def test_load_runtime_config():
    file_path = Path(RUNTIME_TEST_CONFIGS_ROOT / "configs/test_config.yaml").resolve().absolute()
    assert file_path.exists()
    configs = [file_path, str(file_path)]
    configs.extend(DEFAULT_CONFIGS)
    for c in configs:
        config = load_runtime_config(c)
        assert isinstance(config, RuntimeConfig)
        assert Path(config.base_dir).is_absolute()


@pytest.mark.unittest
def test_load_runtime_config_compatibility():
    file_path = Path(RUNTIME_TEST_CONFIGS_ROOT / "configs/test_config_compatibility.yaml").resolve().absolute()
    assert file_path.exists()
    config = load_runtime_config(file_path)
    assert isinstance(config, RuntimeConfig)
    assert Path(config.base_dir).is_absolute()


@pytest.mark.unittest
def test_load_invalid_runtime_config():
    with pytest.raises(ConfigFileNotExists):
        load_runtime_config(RUNTIME_TEST_CONFIGS_ROOT / "configs/not_exist_config.yaml")


@pytest.mark.unittest
def test_runtime_config_to_yaml():
    file_path = Path(RUNTIME_TEST_CONFIGS_ROOT / "configs/test_config.yaml").resolve().absolute()
    c = load_runtime_config(file_path)
    yaml = c.to_yaml()
    f = io.StringIO(yaml)
    c1 = OmegaConf.load(f)
    assert yaml is not None
    assert c.storage.storage_path == c1.storage.storage_path


@pytest.mark.unittest
def test_runtime_config_in_compute_instance():
    sub_id = "96aede12-2f73-41cb-b983-6d11a904839b"
    rg = "promptflow"
    ws = "promptflow-canary"
    tracking_uri = (
        "azureml://eastus2euap.api.azureml.ms/mlflow/v1.0/"
        + f"subscriptions/{sub_id}/resourceGroups/{rg}"
        + f"/providers/Microsoft.MachineLearningServices/workspaces/{ws}"
    )
    with patch.dict(
        os.environ,
        {"MLFLOW_TRACKING_URI": tracking_uri},
    ):
        client = get_mlclient_from_env(cred=get_cred())
        assert client is not None
        assert client.subscription_id == sub_id
        assert client.resource_group_name == rg
        assert client.workspace_name == ws
        c = load_runtime_config()
        assert c is not None
        # assert c.deployment.subscription_id == sub_id
        # assert c.deployment.resource_group == rg
        # assert c.deployment.workspace_name == ws
        # assert c.deployment.mt_service_endpoint == "https://eastus2euap.api.azureml.ms"
        # wks = client.workspaces.get()
        # storage_acc = wks.storage_account.split("/")[-1]
        # assert c.storage.storage_account == storage_acc

    invalid_urls = [
        "invalid://eastus2euap.api.azureml.ms/x/xx/subscriptions/xx/resourceGroups/xx/xx/workspaces/promptflow-canary",
        "invalid_url",
    ]
    for url in invalid_urls:
        with patch.dict(
            os.environ,
            {
                "MLFLOW_TRACKING_URI": url,
            },
        ):
            client = get_mlclient_from_env(cred=get_cred())
            assert client is None

            c = load_runtime_config()
            assert c is not None
            assert not c.storage.storage_account
            assert not c.deployment.mt_service_endpoint


@pytest.mark.unittest
def test_init_from_request_with_workspace_access_token(runtime_config):
    with patch("promptflow.runtime.utils._token_utils.get_echo_credential_from_token"):
        with patch.object(RuntimeConfig, "get_ml_client") as mock_get_client:
            # Mock the get_echo_credential_from_token function
            mock_ml_client = MagicMock()
            mock_keys = MagicMock()
            mock_keys.user_storage_key = "test_key"
            mock_ml_client.workspaces.get_keys.return_value = mock_keys
            mock_get_client.return_value = mock_ml_client

            # Call the init_from_request method with a workspace access token
            runtime_config.init_from_request(workspace_access_token="test_token")

            # Check that the storage account key was set correctly
            assert runtime_config.storage.storage_account_key == "test_key"


@pytest.mark.unittest
def test_init_from_request_with_workspace_access_token_none(runtime_config):
    with patch("promptflow.runtime.utils._token_utils.get_echo_credential_from_token"):
        with patch.object(RuntimeConfig, "get_ml_client") as mock_get_client:
            # mock raise execption
            mock_get_client.side_effect = Exception("test exception")

            runtime_config.init_from_request(workspace_access_token="test_token")
            assert runtime_config.storage.storage_account_key == ""


@pytest.mark.unittest
def test_init_from_request_without_workspace_access_token(runtime_config):
    with patch("promptflow.runtime.utils._token_utils.get_default_credential"):
        with patch.object(RuntimeConfig, "get_ml_client") as mock_get_client:
            # Mock the get_default_credential function
            mock_ml_client = MagicMock()
            mock_keys = MagicMock()
            mock_keys.user_storage_key = "test_key"
            mock_ml_client.workspaces.get_keys.return_value = mock_keys
            mock_get_client.return_value = mock_ml_client

            # Call the init_from_request method without a workspace access token
            runtime_config.init_from_request(None)

            # Check that the storage account key was set correctly
            assert runtime_config.storage.storage_account_key == "test_key"


@pytest.mark.unittest
def test_init_from_request_without_workspace_access_token_none(runtime_config):
    with patch("promptflow.runtime.utils._token_utils.get_default_credential"):
        with patch.object(RuntimeConfig, "get_ml_client") as mock_get_client:
            # mock raise execption
            mock_get_client.side_effect = Exception("test exception")

            runtime_config.init_from_request(None)

            assert runtime_config.storage.storage_account_key == ""


@pytest.mark.unittest
def test_get_azure_ml_run_storage(runtime_config, mocker: MockFixture):
    from azure.core.credentials import AzureNamedKeyCredential
    from azure.core.exceptions import HttpResponseError

    from promptflow.storage.azureml_run_storage import AzureMLRunStorage, MlflowHelper

    runtime_config.init_from_request(None)
    runtime_config.storage.storage_account = "test_storage_account"
    runtime_config.deployment.endpoint_name = "test_endpoint"
    dummy_value = "dummy"
    runtime_config.deployment.subscription_id = dummy_value
    runtime_config.deployment.resource_group = dummy_value
    runtime_config.deployment.workspace_name = dummy_value
    runtime_config.deployment.mt_service_endpoint = dummy_value

    with patch.object(RuntimeConfig, "get_ml_client") as mocked_mlclient:
        # test auth error for role 'AzureML Data Scientist'
        response = MagicMock()
        response.status_code = 403
        mocked_mlclient.return_value.jobs._runs_operations.get_run.side_effect = HttpResponseError(
            "test exception", response=response
        )
        with pytest.raises(UserAuthenticationError) as ex:
            runtime_config.get_run_storage(None)

        assert "Please assign RBAC role 'AzureML Data Scientist'" in str(ex.value)

        # recover the mlclient
        mocked_mlclient.return_value = MagicMock()

        with patch("promptflow.storage.azureml_run_storage.TableServiceClient") as mocked:
            # test auth error for role 'Storage Blob Data Contributor' and 'Storage Table Data Contributor'
            response = MagicMock()
            response.status_code = 403
            mocked.return_value.create_table_if_not_exists.side_effect = HttpResponseError(
                "test exception", response=response
            )
            with pytest.raises(UserErrorException) as ex:
                runtime_config.get_run_storage(None)

            assert "Please assign RBAC role 'Storage Table Data Contributor'" in str(ex.value)

        # mocker.patch.object(runtime_config, "get_and_validate_mlflow_tracking_url")
        mocker.patch.object(AzureMLRunStorage, "init_azure_table_service_client")
        mocker.patch.object(AzureMLRunStorage, "init_azure_blob_service_client")
        mocker.patch.object(MlflowHelper, "__init__", return_value=None)

        # use dummy storage_account_key to get AzureNamedKeyCredential
        runtime_config.storage.storage_account_key = "dummy"
        storage = runtime_config.get_run_storage()

        assert isinstance(storage, AzureMLRunStorage)
        assert not isinstance(storage._ml_client._credential, AzureNamedKeyCredential)


@pytest.mark.unittest
def test_runtime_config_workspace_info_injection():
    # required lines to prepare client with workspace
    sub_id = "96aede12-2f73-41cb-b983-6d11a904839b"
    rg = "promptflow"
    ws = "promptflow-canary"
    tracking_uri = (
        "azureml://eastus2euap.api.azureml.ms/mlflow/v1.0/"
        + f"subscriptions/{sub_id}/resourceGroups/{rg}"
        + f"/providers/Microsoft.MachineLearningServices/workspaces/{ws}"
    )
    with patch.dict(
        os.environ,
        {"MLFLOW_TRACKING_URI": tracking_uri},
    ):
        config = load_runtime_config()
        config.deployment.edition = PromptflowEdition.ENTERPRISE
        config.init_from_request(workspace_access_token=None)
        assert os.environ["AZUREML_ARM_SUBSCRIPTION"] == sub_id
        assert os.environ["AZUREML_ARM_RESOURCEGROUP"] == rg
        assert os.environ["AZUREML_ARM_WORKSPACE_NAME"] == ws

        # Make sure workspace id also get injected
        workspace_id = "5fbfda62-4e3d-43da-b908-8b8feca82b17"
        assert config.deployment.workspace_id == workspace_id


@pytest.mark.unittest
def test_workspace_id_init_from_request():
    sub_id = "96aede12-2f73-41cb-b983-6d11a904839b"
    rg = "promptflow"
    ws = "promptflow-canary"

    with patch.object(RuntimeConfig, "_populate_default_config_from_env"):
        config = load_runtime_config()
        config.deployment.workspace_name = ws
        config.deployment.resource_group = rg
        config.deployment.subscription_id = sub_id
        config.init_from_request(workspace_access_token=None)
        workspace_id = "5fbfda62-4e3d-43da-b908-8b8feca82b17"
        assert config.deployment.workspace_id == workspace_id


@pytest.mark.unittest
def test_get_storage_from_config():
    from promptflow.runtime.utils._utils import get_storage_from_config

    config = load_runtime_config()
    storage1 = get_storage_from_config(config)
    storage2 = get_storage_from_config(config)
    assert id(storage1) == id(storage2)


@pytest.mark.unittest
def test_get_worskpace_config():
    sub_id = "96aede12-2f73-41cb-b983-6d11a904839b"
    rg = "promptflow"
    ws = "promptflow-canary"
    tracking_uri = (
        "azureml://eastus2euap.api.azureml.ms/mlflow/v1.0/"
        + f"subscriptions/{sub_id}/resourceGroups/{rg}"
        + f"/providers/Microsoft.MachineLearningServices/workspaces/{ws}"
    )
    with patch.dict(
        os.environ,
        {"MLFLOW_TRACKING_URI": tracking_uri},
    ):
        client = get_mlclient_from_env(cred=get_cred())
        config = get_workspace_config(client, logger=test_logger)

        assert config == {
            "mt_service_endpoint": "https://eastus2euap.api.azureml.ms",
            "resource_group": "promptflow",
            "storage_account": "promptflowcana4560041206",
            "subscription_id": "96aede12-2f73-41cb-b983-6d11a904839b",
            "workspace_id": "5fbfda62-4e3d-43da-b908-8b8feca82b17",
            "workspace_name": "promptflow-canary",
        }


@pytest.mark.unittest
def test_runtime_compute():
    # Test compute instance path
    with patch.dict(
        os.environ,
        {"CI_NAME": "mock"},
    ):
        config = load_runtime_config()
        assert config.deployment.compute_type == ComputeType.COMPUTE_INSTANCE
    # Test MIR path
    config = load_runtime_config(file="mir")
    assert config.deployment.compute_type == ComputeType.MANAGED_ONLINE_DEPLOYMENT
    # Test mock local path
    file_path = Path(RUNTIME_TEST_CONFIGS_ROOT / "configs/test_config_local.yaml").resolve().absolute()
    config = load_runtime_config(file_path)
    assert config.deployment.compute_type == ComputeType.LOCAL


@pytest.mark.unittest
def test_init_workspace_id():
    sub_id = "96aede12-2f73-41cb-b983-6d11a904839b"
    rg = "promptflow"
    ws = "promptflow-canary"
    tracking_uri = (
        "azureml://eastus2euap.api.azureml.ms/mlflow/v1.0/"
        + f"subscriptions/{sub_id}/resourceGroups/{rg}"
        + f"/providers/Microsoft.MachineLearningServices/workspaces/{ws}"
    )
    with patch.dict(
        os.environ,
        {"MLFLOW_TRACKING_URI": tracking_uri},
    ):
        config = load_runtime_config(args=["deployment.edition=enterprise"])
        workspace_id = "5fbfda62-4e3d-43da-b908-8b8feca82b17"
        assert config.deployment.workspace_id == workspace_id


@pytest.mark.unittest
def test_runtime_name():
    config = load_runtime_config()
    # runtime's empty when not configured
    assert config.deployment.runtime_name == ""

    runtime_name = "test_runtime_name"
    config = load_runtime_config(args=[f"deployment.runtime_name={runtime_name}"])
    assert config.deployment.runtime_name == runtime_name
