# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import pytest
from azure.core.exceptions import HttpResponseError
from promptflow.exceptions import _ErrorInfo, ErrorCategory, ErrorTarget, UserErrorException
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
        error_category, error_type, error_target, error_message = _ErrorInfo.get_error_info(ex)
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
        error_category, error_type, error_target, error_message = _ErrorInfo.get_error_info(ex)
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
        error_category, error_type, error_target, error_message = _ErrorInfo.get_error_info(ex)
        assert error_category == ErrorCategory.SystemError
        assert error_type == "HttpResponseError"
        assert error_target == ErrorTarget.UNKNOWN
        assert (
            "exception msg=Non promptflow message, not recorded., "
            "exception module=Non promptflow module, not recorded., "
            "exception code=Non promptflow code, not recorded., "
            "exception lineno=Non promptflow code lineno, not recorded."
        ) in error_message

    def test_error_category_with_status_code1(self, subscription_id, resource_group_name, workspace_name):
        """Raise a Exception and it has status_code, whose status_code non 4XX, it should be SystemError."""

        try:
            raise Exception()
        except Exception as e:
            e.status_code = 300
            ex = e
        error_category, error_type, error_target, error_message = _ErrorInfo.get_error_info(ex)
        assert error_category == ErrorCategory.SystemError
        assert error_type == "Exception"
        assert error_target == ErrorTarget.UNKNOWN
        assert (
            "exception msg=Non promptflow message, not recorded., "
            "exception module=Non promptflow module, not recorded., "
            "exception code=Non promptflow code, not recorded., "
            "exception lineno=Non promptflow code lineno, not recorded."
        ) in error_message

    def test_error_category_with_status_code2(self, subscription_id, resource_group_name, workspace_name):
        """Raise a Exception and it has status_code, whose status_code is 4XX, it should be UserError."""

        try:
            raise Exception()
        except Exception as e:
            e.status_code = 400
            ex = e
        error_category, error_type, error_target, error_message = _ErrorInfo.get_error_info(ex)
        assert error_category == ErrorCategory.UserError
        assert error_type == "Exception"
        assert error_target == ErrorTarget.UNKNOWN
        assert (
            "exception msg=Non promptflow message, not recorded., "
            "exception module=Non promptflow module, not recorded., "
            "exception code=Non promptflow code, not recorded., "
            "exception lineno=Non promptflow code lineno, not recorded."
        ) in error_message

    def test_error_category_with_status_code3(self, subscription_id, resource_group_name, workspace_name):
        """Raise a Exception and it has status_code, whose status_code is 429, it should be SystemError."""

        try:
            raise Exception()
        except Exception as e:
            e.status_code = 429
            ex = e
        error_category, error_type, error_target, error_message = _ErrorInfo.get_error_info(ex)
        assert error_category == ErrorCategory.SystemError
        assert error_type == "Exception"
        assert error_target == ErrorTarget.UNKNOWN
        assert (
            "exception msg=Non promptflow message, not recorded., "
            "exception module=Non promptflow module, not recorded., "
            "exception code=Non promptflow code, not recorded., "
            "exception lineno=Non promptflow code lineno, not recorded."
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
        error_category, error_type, error_target, error_message = _ErrorInfo.get_error_info(ex)
        assert error_category == ErrorCategory.UserError
        assert error_type == "InvalidNodeReference"
        assert error_target == ErrorTarget.EXECUTOR
        assert (
            "exception msg=Non promptflow message, not recorded., "
            "exception module=Non promptflow module, not recorded., "
            "exception code=Non promptflow code, not recorded., "
            "exception lineno=Non promptflow code lineno, not recorded."
        ) in error_message

    def test_error_category_with_cause_exception1(self):
        """cause exception is PromptflowException and e is PromptflowException, recording cause exception."""

        ex = None
        try:
            try:
                FlowValidator._validate_aggregation_inputs({}, {"input1": "value1"})
            except Exception as e:
                raise UserErrorException("FlowValidator._validate_aggregation_inputs failed") from e
        except Exception as e:
            ex = e
        error_category, error_type, error_target, error_message = _ErrorInfo.get_error_info(ex)
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

    def test_error_category_with_cause_exception2(self, pf):
        """cause exception is not PromptflowException and e is PromptflowException, recording e exception."""

        ex = None
        try:
            try:
                pf.run("./exceptions/flows")
            except Exception as e:
                raise UserErrorException("pf run failed") from e
        except Exception as e:
            ex = e
        error_category, error_type, error_target, error_message = _ErrorInfo.get_error_info(ex)
        assert error_category == ErrorCategory.UserError
        assert error_type == "UserErrorException"
        assert error_target == ErrorTarget.UNKNOWN
        assert (
            "exception msg=Non promptflow message, not recorded., "
            "exception module=Non promptflow module, not recorded., "
            "exception code=Non promptflow code, not recorded., "
            "exception lineno=Non promptflow code lineno, not recorded."
        ) in error_message

    def test_error_category_with_cause_exception3(self, pf):
        """cause exception is not PromptflowException and e is not PromptflowException, recording cause exception."""

        ex = None
        try:
            try:
                pf.run("./exceptions/flows")
            except Exception as e:
                raise Exception("pf run failed") from e
        except Exception as e:
            ex = e
        error_category, error_type, error_target, error_message = _ErrorInfo.get_error_info(ex)
        assert error_category == ErrorCategory.UserError
        assert error_type == "FileNotFoundError"
        assert error_target == ErrorTarget.UNKNOWN
        assert (
            "exception msg=, "
            "exception module=promptflow._sdk._pf_client, "
            'exception code=raise FileNotFoundError(f"flow path {flow} does not exist"), '
            "exception lineno="
        ) in error_message
