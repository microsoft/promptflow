# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import pytest

from promptflow.azure import PFClient
from promptflow.azure.operations._arm_connection_operations import ArmConnectionOperations

from .._recording_base import ARMConnectionOperationsIntegrationTestCase
from .._recording_utils import fixture_provider


@pytest.fixture(scope="class")
def connection_ops(request: pytest.FixtureRequest, pf: PFClient) -> ArmConnectionOperations:
    request.cls.connection_ops = pf._arm_connections
    return request.cls.connection_ops


@pytest.mark.usefixtures("connection_ops")
@pytest.mark.e2etest
class TestArmConnectionOperations(ARMConnectionOperationsIntegrationTestCase):
    @fixture_provider
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
