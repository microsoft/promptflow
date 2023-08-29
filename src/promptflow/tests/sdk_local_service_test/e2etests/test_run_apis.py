# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import pytest
import requests


@pytest.mark.e2etest
class TestRunAPIs:
    def test_heartbeat(self) -> None:
        response = requests.get("http://localhost:5000/heartbeat")
        assert response.status_code == 204
