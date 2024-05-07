# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import uuid

import pytest

from promptflow._sdk._version import VERSION
from promptflow._sdk.entities import CustomConnection
from promptflow.client import PFClient

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
        base_user_agent = [f"local_pfs/{VERSION}"]
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

        with check_activity_end_telemetry(expected_activities=[]):
            conn_from_pfs = pfs_op.connection_operation_with_invalid_user(name=name)
        assert conn_from_pfs.status_code == 403

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

    def test_get_connection_specs(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(expected_activities=[]):
            specs = pfs_op.get_connection_specs(status_code=200).json
        assert len(specs) > 1
