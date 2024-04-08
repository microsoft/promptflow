# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from unittest import mock

import pytest

from promptflow.azure._utils._tracing import _init_workspace_cosmos_db


@pytest.mark.sdk_test
@pytest.mark.unittest
class TestLocalToCloud:
    def test_init_workspace_cosmos_db_timeout(self) -> None:
        def mock_failed_init_cosmos_func() -> None:
            return None

        with mock.patch("promptflow.azure._utils._tracing.COSMOS_INIT_POLL_TIMEOUT_SECOND", 2), mock.patch(
            "promptflow.azure._utils._tracing.COSMOS_INIT_POLL_INTERVAL_SECOND", 1
        ):
            with pytest.raises(Exception) as e:
                _init_workspace_cosmos_db(init_cosmos_func=mock_failed_init_cosmos_func)
            assert "please wait for a while and retry." in str(e)
