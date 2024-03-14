# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import pytest


@pytest.mark.unittest
class TestStartTrace:
    def test_import(self):
        from promptflow.tracing import start_trace

        assert callable(start_trace)

    def test_adhoc_for_coverage(self):
        from promptflow.tracing import start_trace, trace

        start_trace()
        trace()
