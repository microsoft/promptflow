# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import pytest
from azure.core.exceptions import HttpResponseError
from promptflow.exceptions import ErrorInfo, ErrorCategory, ErrorTarget
from promptflow.executor import FlowValidator
from promptflow.executor._errors import InvalidNodeReference

FLOWS_DIR = "./tests/test_configs/flows/print_input_flow"


@pytest.mark.unittest
class TestExceptions:
    def test_error_category_with_user_error(self, pf):
        ex = None
        try:
            pf.run("./exceptions/flows")
        except Exception as e:
            ex = e
        error_category, error_type, error_target, error_message = ErrorInfo.get_error_info(ex)
        assert error_category == ErrorCategory.UserError
        assert error_type == "FileNotFoundError"
        assert error_target == ErrorTarget.UNKNOWN
        assert (
            "exception msg=, "
            "exception module=promptflow._sdk._pf_client, "
            'exception code=raise FileNotFoundError(f"flow path {flow} does not exist"), '
            "exception lineno="
        ) in error_message

    def test_error_category_with_system_error(self):
        ex = None
        try:
            FlowValidator._validate_aggregation_inputs({}, {"input1": "value1"})
        except Exception as e:
            ex = e
        error_category, error_type, error_target, error_message = ErrorInfo.get_error_info(ex)
        assert error_category == ErrorCategory.SystemError
        assert error_type == "InvalidAggregationInput"
        assert error_target == ErrorTarget.UNKNOWN
        assert (
            "exception msg=The input for aggregation is incorrect. "
            "The value for aggregated reference input '{input_key}' "
            "should be a list, but received {value_type}. "
            "Please adjust the input value to match the expected format., "
            "exception module=promptflow.executor.flow_validator, "
            "exception code=raise InvalidAggregationInput(, "
            "exception lineno="
        ) in error_message

    def test_error_category_with_http_error(self, subscription_id, resource_group_name, workspace_name):
        try:
            raise HttpResponseError(message="HttpResponseError")
        except Exception as e:
            ex = e
        error_category, error_type, error_target, error_message = ErrorInfo.get_error_info(ex)
        assert error_category == ErrorCategory.SystemError
        assert error_type == "HttpResponseError"
        assert error_target == ErrorTarget.UNKNOWN
        assert (
            "exception msg=, "
            "exception module=sdk_cli_test.unittests.test_exceptions, "
            'exception code=raise HttpResponseError(message="HttpResponseError"), '
            "exception lineno="
        ) in error_message

    def test_error_category_with_executor_error(self):
        try:
            msg_format = (
                "Invalid node definitions found in the flow graph. Non-aggregation node '{invalid_reference}' "
                "cannot be referenced in the activate config of the aggregation node '{node_name}'. Please "
                "review and rectify the node reference."
            )
            raise InvalidNodeReference(message_format=msg_format, invalid_reference=None, node_name="node_name")
        except Exception as e:
            ex = e
        error_category, error_type, error_target, error_message = ErrorInfo.get_error_info(ex)
        assert error_category == ErrorCategory.UserError
        assert error_type == "InvalidNodeReference"
        assert error_target == ErrorTarget.EXECUTOR
        assert (
            "exception msg=Invalid node definitions found in the flow graph. "
            "Non-aggregation node '{invalid_reference}' cannot be referenced in the activate "
            "config of the aggregation node '{node_name}'. "
            "Please review and rectify the node reference., "
            "exception module=sdk_cli_test.unittests.test_exceptions, "
            "exception code=raise InvalidNodeReference(message_format=msg_format, "
            'invalid_reference=None, node_name="node_name"), '
            "exception lineno="
        ) in error_message
