# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import pytest

from promptflow._sdk._service.utils.utils import get_pfs_version

from ..utils import PFSOperations


@pytest.mark.e2etest
class TestGeneralAPIs:
    def test_heartbeat(self, pfs_op: PFSOperations) -> None:
        response = pfs_op.heartbeat()
        assert response.status_code == 200
        response_json = response.json
        assert isinstance(response_json, dict)
        assert "promptflow" in response_json
        assert response_json["promptflow"] == get_pfs_version()

    def test_rootpage_redirect(self, pfs_op: PFSOperations) -> None:
        response = pfs_op.root_page()
        assert response.status_code == 302
