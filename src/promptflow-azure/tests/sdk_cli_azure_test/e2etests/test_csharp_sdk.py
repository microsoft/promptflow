# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Callable

import pytest

from promptflow._sdk.entities import Run
from promptflow.azure import PFClient

from .._azure_utils import DEFAULT_TEST_TIMEOUT, PYTEST_TIMEOUT_METHOD


@pytest.mark.timeout(timeout=DEFAULT_TEST_TIMEOUT, method=PYTEST_TIMEOUT_METHOD)
@pytest.mark.e2etest
@pytest.mark.csharp
@pytest.mark.usefixtures(
    "mock_set_headers_with_user_aml_token",
    "single_worker_thread_pool",
    "vcr_recording",
)
class TestCSharpSdk:
    def test_basic_run_bulk(self, pf: PFClient, randstr: Callable[[str], str], csharp_test_project_basic):
        name = randstr("name")

        run = pf.run(
            flow=csharp_test_project_basic["flow_dir"],
            data=csharp_test_project_basic["data"],
            name=name,
        )
        assert isinstance(run, Run)
        assert run.name == name
