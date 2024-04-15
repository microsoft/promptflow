# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import pytest
from flask.app import Flask

from promptflow.client import PFClient

from .utils import PFSOperations


@pytest.fixture
def app() -> Flask:
    from promptflow._sdk._service.app import create_app

    app, _ = create_app()
    app.config.update({"TESTING": True})
    yield app


@pytest.fixture
def pfs_op(app: Flask) -> PFSOperations:
    client = app.test_client()
    return PFSOperations(client)


@pytest.fixture(scope="session")
def pf_client() -> PFClient:
    return PFClient()
