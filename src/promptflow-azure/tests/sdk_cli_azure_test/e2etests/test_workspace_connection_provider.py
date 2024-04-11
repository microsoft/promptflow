# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import pytest

from promptflow.core._connection import _Connection
from promptflow.core._connection_provider._workspace_connection_provider import WorkspaceConnectionProvider

from .._azure_utils import DEFAULT_TEST_TIMEOUT, PYTEST_TIMEOUT_METHOD


@pytest.mark.timeout(timeout=DEFAULT_TEST_TIMEOUT, method=PYTEST_TIMEOUT_METHOD)
@pytest.mark.e2etest
@pytest.mark.usefixtures("vcr_recording", "pf")
class TestWorkspaceConnectionProvider:
    # Note: Get covered in test_arm_connection_operations.py
    def test_list_connections(self, pf):
        provider = WorkspaceConnectionProvider(
            subscription_id=pf._ml_client._operation_scope.subscription_id,
            resource_group_name=pf._ml_client._operation_scope.resource_group_name,
            workspace_name=pf._ml_client._operation_scope.workspace_name,
            credential=pf._ml_client._credential,
        )
        connections = provider.list()
        assert len(connections) > 0
        assert all(isinstance(connection, _Connection) for connection in connections)
