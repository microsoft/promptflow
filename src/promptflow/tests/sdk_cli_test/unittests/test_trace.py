# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import pytest

from promptflow._constants import TRACE_SESSION_ID_OP_CTX_NAME
from promptflow._core.operation_context import OperationContext
from promptflow._trace._start_trace import _provision_session


@pytest.mark.sdk_test
@pytest.mark.unittest
class TestTrace:
    def test_session_id_in_operation_context(self):
        session_id = _provision_session()
        operation_context = OperationContext.get_instance()
        assert session_id == operation_context[TRACE_SESSION_ID_OP_CTX_NAME]

    def test_provision_session_multiple_times(self):
        session_id = _provision_session()
        session_id_twice = _provision_session()
        assert session_id == session_id_twice
