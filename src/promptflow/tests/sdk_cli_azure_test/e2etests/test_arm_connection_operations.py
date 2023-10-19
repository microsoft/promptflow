# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import pytest

from .._azure_utils import DEFAULT_TEST_TIMEOUT, PYTEST_TIMEOUT_METHOD


@pytest.fixture
def connection_ops(ml_client):
    from promptflow.azure import PFClient

    pf = PFClient(ml_client=ml_client)
    yield pf._arm_connections


@pytest.mark.timeout(timeout=DEFAULT_TEST_TIMEOUT, method=PYTEST_TIMEOUT_METHOD)
@pytest.mark.e2etest
class TestArmConnectionOperations:
    def test_get_connection(self, connection_ops):
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
