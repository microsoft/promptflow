# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import pytest
from promptflow._sdk._pf_client import PFClient
from promptflow.exceptions import ErrorInfo, ErrorCategory, ErrorType, ErrorTarget

FLOWS_DIR = "./tests/test_configs/flows"
CONNECTIONS_DIR = "./tests/test_configs/connections"
DATAS_DIR = "./tests/test_configs/datas"


@pytest.mark.unittest
class TestExceptions:
    @pytest.fixture(autouse=True)
    def init(self):
        self.pf_client = PFClient()

    def test_error_category_with_user_error(self):
        ex = None
        try:
            self.pf_client.run("./exceptions/flows")
        except Exception as e:
            ex = e
        assert isinstance(ex, FileNotFoundError)
        error_category, error_type, error_target, error_message = ErrorInfo.get_error_info(ex)
        assert error_category == ErrorCategory.SDKUserError
        assert error_type == ErrorType.SDKError
        assert error_target == ErrorTarget.UNKNOWN
        assert error_message == (
            "exception name=FileNotFoundError, "
            "exception msg=, "
            "exception module=promptflow._sdk._pf_client, "
            'exception code=raise FileNotFoundError(f"flow path {flow} does not exist"), '
            "exception lineno=107"
        )

    def test_error_category_with_sdk_error(self):
        pass

    def test_error_category_with_system_error(self):
        pass

    def test_error_category_with_executor_error(self):
        pass

    def test_error_category_with_pfs_error(self):
        pass

    def test_error_category_with_http_error(self):
        pass

    def test_error_category_with_cause_error(self):
        pass
