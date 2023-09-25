# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import pytest

from promptflow._sdk._utils import get_promptflow_sdk_version

from ..utils import PFSOperations


@pytest.mark.e2etest
class TestGeneralAPIs:
    def test_heartbeat(self, pfs_op: PFSOperations) -> None:
        response = pfs_op.heartbeat()
        assert response.status_code == 200
        response_json = response.json
        assert isinstance(response_json, dict)
        assert "sdk_version" in response_json
        assert response_json["sdk_version"] == get_promptflow_sdk_version()
