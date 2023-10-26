# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import pytest

from promptflow.azure import PFClient
from promptflow.azure.operations._arm_connection_operations import ArmConnectionOperations

from .._azure_utils import DEFAULT_TEST_TIMEOUT, PYTEST_TIMEOUT_METHOD


@pytest.fixture
def connection_ops(pf: PFClient) -> ArmConnectionOperations:
    return pf._arm_connections


@pytest.mark.timeout(timeout=DEFAULT_TEST_TIMEOUT, method=PYTEST_TIMEOUT_METHOD)
@pytest.mark.e2etest
@pytest.mark.usefixtures("vcr_recording")
class TestArmConnectionOperations:
    def test_get_connection(self, connection_ops: ArmConnectionOperations):
        # Note: Secrets will be returned by arm api
        result = connection_ops.get(name="azure_open_ai_connection")
        assert (
            result._to_dict().items()
            > {
                "api_type": "azure",
                "module": "promptflow.connections",
                "name": "azure_open_ai_connection",
            }.items()
        )

        result = connection_ops.get(name="custom_connection")
        assert (
            result._to_dict().items()
            > {
                "name": "custom_connection",
                "module": "promptflow.connections",
                "configs": {},
            }.items()
        )
