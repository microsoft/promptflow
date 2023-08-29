# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import pytest

from promptflow import PFClient


@pytest.fixture(scope="session")
def pf_client() -> PFClient:
    return PFClient()
