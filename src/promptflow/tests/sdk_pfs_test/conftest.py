# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
from pathlib import Path

import pytest

from promptflow import PFClient
from promptflow._sdk.entities import AzureOpenAIConnection
from promptflow._sdk.entities._connection import _Connection as Connection
from promptflow._utils.utils import is_in_ci_pipeline

from .utils import PFSOperations, start_pfs, stop_pfs

PROMOTFLOW_ROOT = Path(__file__) / "../../.."
CONNECTION_FILE = (PROMOTFLOW_ROOT / "connections.json").resolve().absolute().as_posix()


@pytest.fixture(scope="session", autouse=True)
def pfs() -> None:
    if is_in_ci_pipeline():
        yield
    else:
        start_pfs()
        yield
        stop_pfs()


@pytest.fixture(scope="session")
def pf_client() -> PFClient:
    return PFClient()


@pytest.fixture(scope="session")
def pfs_op() -> PFSOperations:
    return PFSOperations()


_connection_setup = False


@pytest.fixture
def setup_local_connection(pf_client: PFClient):
    global _connection_setup
    if _connection_setup:
        return
    connection_dict = json.loads(open(CONNECTION_FILE, "r").read())
    for name, _dct in connection_dict.items():
        if _dct["type"] == "BingConnection":
            continue
        pf_client.connections.create_or_update(Connection.from_execution_connection_dict(name=name, data=_dct))
    _connection_setup = True


@pytest.fixture
def local_aoai_connection(pf_client: PFClient, azure_open_ai_connection: AzureOpenAIConnection) -> Connection:
    conn = AzureOpenAIConnection(
        name="azure_open_ai_connection",
        api_key=azure_open_ai_connection.api_key,
        api_base=azure_open_ai_connection.api_base,
    )
    pf_client.connections.create_or_update(conn)
    return conn
