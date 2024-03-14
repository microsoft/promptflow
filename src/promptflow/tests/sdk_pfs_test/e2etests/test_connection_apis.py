# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
import tempfile
import uuid
from pathlib import Path

import mock
import pytest
from sdk_cli_azure_test.recording_utilities import is_replay

from promptflow import PFClient
from promptflow._sdk.entities import CustomConnection

from ..utils import PFSOperations, check_activity_end_telemetry


def create_custom_connection(client: PFClient) -> str:
    name = str(uuid.uuid4())
    connection = CustomConnection(name=name, configs={"api_base": "test"}, secrets={"api_key": "test"})
    client.connections.create_or_update(connection)
    return name


@pytest.mark.e2etest
class TestConnectionAPIs:
    def test_list_connections(self, pf_client: PFClient, pfs_op: PFSOperations) -> None:
        create_custom_connection(pf_client)
        with check_activity_end_telemetry(activity_name="pf.connections.list"):
            connections = pfs_op.list_connections().json

        assert len(connections) >= 1

    def test_list_connections_with_different_user_agent(self, pf_client: PFClient, pfs_op: PFSOperations) -> None:
        create_custom_connection(pf_client)
        base_user_agent = ["local_pfs/0.0.1"]
        for _, extra_user_agent in enumerate(
            [
                ["another_test_user_agent/0.0.1"],
                ["test_user_agent/0.0.1"],
                ["another_test_user_agent/0.0.1"],
                ["test_user_agent/0.0.1"],
            ]
        ):
            with check_activity_end_telemetry(
                activity_name="pf.connections.list", user_agent=base_user_agent + extra_user_agent
            ):
                pfs_op.list_connections(user_agent=extra_user_agent)

    def test_get_connection(self, pf_client: PFClient, pfs_op: PFSOperations) -> None:
        name = create_custom_connection(pf_client)
        with check_activity_end_telemetry(activity_name="pf.connections.get"):
            conn_from_pfs = pfs_op.get_connection(name=name, status_code=200).json
        assert conn_from_pfs["name"] == name
        assert conn_from_pfs["configs"]["api_base"] == "test"
        assert "api_key" in conn_from_pfs["secrets"]

        # get connection with secret
        with check_activity_end_telemetry(activity_name="pf.connections.get"):
            conn_from_pfs = pfs_op.get_connection_with_secret(name=name, status_code=200).json
        assert not conn_from_pfs["secrets"]["api_key"].startswith("*")

    def test_delete_connection(self, pf_client: PFClient, pfs_op: PFSOperations) -> None:
        len_connections = len(pfs_op.list_connections().json)

        name = create_custom_connection(pf_client)
        with check_activity_end_telemetry(
            expected_activities=[
                {"activity_name": "pf.connections.delete", "first_call": True},
            ]
        ):
            pfs_op.delete_connection(name=name, status_code=204)
        len_connections_after = len(pfs_op.list_connections().json)
        assert len_connections_after == len_connections

    def test_list_connection_with_invalid_user(self, pfs_op: PFSOperations) -> None:
        # TODO: should we record telemetry for this case?
        with check_activity_end_telemetry(expected_activities=[]):
            conn_from_pfs = pfs_op.connection_operation_with_invalid_user()
        assert conn_from_pfs.status_code == 403

    def test_get_connection_specs(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(expected_activities=[]):
            specs = pfs_op.get_connection_specs(status_code=200).json
        assert len(specs) > 1

    @pytest.mark.skipif(is_replay(), reason="connection provider test, skip in non-live mode.")
    def test_get_connection_by_provicer(self, pfs_op, subscription_id, resource_group_name, workspace_name):
        target = "promptflow._sdk._pf_client.Configuration.get_connection_provider"
        provider_url_target = (
            "promptflow._sdk.operations._local_azure_connection_operations."
            "LocalAzureConnectionOperations._extract_workspace"
        )
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
