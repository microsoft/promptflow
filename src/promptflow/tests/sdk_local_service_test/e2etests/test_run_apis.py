# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import pytest
import requests


@pytest.mark.e2etest
class TestRunAPIs:
    def test_heartbeat() -> None:
        response = requests.get("localhost:5000/heartbeat")
        assert response.status_code == 204
