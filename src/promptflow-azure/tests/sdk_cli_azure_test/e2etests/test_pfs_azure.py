import json
import tempfile
from pathlib import Path

import mock
import pytest
from _constants import PROMPTFLOW_ROOT
from flask.app import Flask


@pytest.fixture
def app() -> Flask:
    from promptflow._sdk._service.app import create_app

    app, _ = create_app()
    app.config.update({"TESTING": True})
    yield app


@pytest.fixture
def pfs_op(app: Flask):
    # Hack to import the pfs test utils from the devkit tests
    import sys

    temp_path = (
        Path(PROMPTFLOW_ROOT)
        .joinpath("..", "promptflow-devkit", "tests", "sdk_pfs_test")
        .resolve()
        .absolute()
        .as_posix()
    )
    sys.path.append(temp_path)
    # TODO: avoid doing this as utils is a widely used module name
    from utils import PFSOperations

    client = app.test_client()
    return PFSOperations(client)


@pytest.mark.e2etest
class TestPFSAzure:
    @pytest.mark.skipif(pytest.is_replay, reason="connection provider test, skip in non-live mode.")
    def test_get_connection_by_provider(self, pfs_op, subscription_id, resource_group_name, workspace_name):
        target = "promptflow._sdk._pf_client.Configuration.get_connection_provider"
        provider_url_target = "promptflow.core._utils.extract_workspace"
        mock_provider_url = (subscription_id, resource_group_name, workspace_name)
        with mock.patch(target) as mocked_config, mock.patch(provider_url_target) as mocked_provider_url:
            mocked_config.return_value = "azureml"
            mocked_provider_url.return_value = mock_provider_url
            connections = pfs_op.list_connections(status_code=200).json
            assert len(connections) > 0

            connection = pfs_op.get_connection(name=connections[0]["name"], status_code=200).json
            assert connection["name"] == connections[0]["name"]

        target = "promptflow._sdk._pf_client.Configuration.get_config"
        with tempfile.TemporaryDirectory() as temp:
            config_file = Path(temp) / ".azureml" / "config.json"
            config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(config_file, "w") as f:
                config = {
                    "subscription_id": subscription_id,
                    "resource_group": resource_group_name,
                    "workspace_name": workspace_name,
                }
                json.dump(config, f)
            with mock.patch(target) as mocked_config:
                mocked_config.return_value = "azureml"
                connections = pfs_op.list_connections_by_provider(working_dir=temp, status_code=200).json
                assert len(connections) > 0

                connection = pfs_op.get_connections_by_provider(
                    name=connections[0]["name"], working_dir=temp, status_code=200
                ).json
                assert connection["name"] == connections[0]["name"]

                # this test checked 2 cases:
                # 1. if the working directory is not exist, it should return 400
                # 2. working directory has been encoded and decoded correctly, so that previous call may pass validation
                error_message = pfs_op.list_connections_by_provider(
                    working_dir=temp + "not exist", status_code=400
                ).json
                assert error_message == {
                    "errors": {"working_directory": "Invalid working directory."},
                    "message": "Input payload validation failed",
                }
