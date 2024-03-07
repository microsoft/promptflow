# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import pytest
from pytest_mock import MockerFixture

import promptflow.tracing._start_trace
from promptflow._sdk._configuration import Configuration
from promptflow.tracing import start_trace
from promptflow.tracing._constants import PF_TRACING_SKIP_LOCAL_SETUP


@pytest.mark.unittest
class TestStartTrace:
    def test_skip_tracing_local_setup(self, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
        spy = mocker.spy(promptflow.tracing._start_trace, "_tracing_local_setup")
        with mocker.patch.object(Configuration, "is_internal_features_enabled", return_value=True):
            # configured environ to skip local setup
            with monkeypatch.context() as m:
                m.setenv(PF_TRACING_SKIP_LOCAL_SETUP, "true")
                start_trace()
                assert spy.call_count == 0
            # no environ, should call local setup once
            start_trace()
            assert spy.call_count == 1
