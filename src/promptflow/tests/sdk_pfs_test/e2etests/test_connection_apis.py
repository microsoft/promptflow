# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import uuid

import pytest

from promptflow import PFClient
from promptflow._sdk.entities import CustomConnection

from ..utils import PFSOperations


def create_custom_connection(client: PFClient) -> str:
    name = str(uuid.uuid4())
    connection = CustomConnection(name=name, configs={"api_base": "test"}, secrets={"api_key": "test"})
    client.connections.create_or_update(connection)
    return name


@pytest.mark.e2etest
class TestConnectionAPIs:
    def test_list_connections(self, pf_client: PFClient, pfs_op: PFSOperations) -> None:
        create_custom_connection(pf_client)
        connections = pfs_op.list_connections().json
        assert len(connections) >= 1

    def test_get_connection(self, pf_client: PFClient, pfs_op: PFSOperations) -> None:
        name = create_custom_connection(pf_client)
        conn_from_pfs = pfs_op.get_connection(name=name).json
        assert conn_from_pfs["name"] == name
        assert conn_from_pfs["configs"]["api_base"] == "test"
        assert "api_key" in conn_from_pfs["secrets"]
