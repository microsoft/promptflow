# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import pytest

from promptflow import PFClient
from promptflow._sdk.entities import AzureOpenAIConnection
from promptflow._sdk.entities._connection import _Connection as Connection

from .utils import LocalServiceOperations


@pytest.fixture(scope="session")
def pf_client() -> PFClient:
    return PFClient()


@pytest.fixture(scope="session")
def local_service_op() -> LocalServiceOperations:
    return LocalServiceOperations()


@pytest.fixture()
def local_aoai_connection(pf_client: PFClient, azure_open_ai_connection) -> Connection:
    conn = AzureOpenAIConnection(
        name="azure_open_ai_connection",
        api_key=azure_open_ai_connection.api_key,
        api_base=azure_open_ai_connection.api_base,
    )
    pf_client.connections.create_or_update(conn)
    return conn
