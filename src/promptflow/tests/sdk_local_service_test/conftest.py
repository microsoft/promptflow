# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import pytest

from promptflow import PFClient

from .utils import LocalServiceOperations


@pytest.fixture(scope="session")
def pf_client() -> PFClient:
    return PFClient()


@pytest.fixture(scope="session")
def local_service_op() -> LocalServiceOperations:
    return LocalServiceOperations()
