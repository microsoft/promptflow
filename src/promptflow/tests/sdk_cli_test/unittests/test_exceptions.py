# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import re

import pytest
from azure.core.exceptions import HttpResponseError
from promptflow._sdk._orm import RunInfo
from promptflow.exceptions import _ErrorInfo, ErrorCategory, ErrorTarget, UserErrorException
from promptflow.executor import FlowValidator
from promptflow.executor._errors import InvalidNodeReference

FLOWS_DIR = "./tests/test_configs/flows/print_input_flow"


def is_matching(str_a, str_b):
    str_a = re.sub(r"line \d+", r"", str_a)
    str_b = re.sub(r"line \d+", r"", str_b)

    return str_a == str_b


@pytest.mark.unittest
class TestExceptions:
    def test_error_category_with_user_error(self, pf):
        ex = None
        try:
            RunInfo.get("run_name")
        except Exception as e:
            ex = e
        error_category, error_type, error_target, error_message, error_detail = _ErrorInfo.get_error_info(ex)
        assert error_category == ErrorCategory.USER_ERROR
        assert error_type == "RunNotFoundError"
        assert error_target == ErrorTarget.CONTROL_PLANE_SDK
        assert error_message == ""
        assert is_matching(
            "promptflow._sdk._orm.retry, line 43, "
            "return f(*args, **kwargs)\n"
            "promptflow._sdk._orm.run_info, line 142, "
            'raise RunNotFoundError(f"Run name {name!r} cannot be found.")\n',
            error_detail,
        )

    def test_error_category_with_system_error(self):
        ex = None
        try:
            FlowValidator._validate_aggregation_inputs({}, {"input1": "value1"})
        except Exception as e:
            ex = e
        error_category, error_type, error_target, error_message, error_detail = _ErrorInfo.get_error_info(ex)
        assert error_category == ErrorCategory.SYSTEM_ERROR
        assert error_type == "InvalidAggregationInput"
        assert error_target == ErrorTarget.EXECUTOR
        assert error_message == (
            "The input for aggregation is incorrect. "
            "The value for aggregated reference input '{input_key}' should be a list, "
            "but received {value_type}. "
            "Please adjust the input value to match the expected format."
        )
        assert is_matching(
            "promptflow.executor.flow_validator, line 311, raise InvalidAggregationInput(\n", error_detail
        )

    def test_error_category_with_http_error(self, subscription_id, resource_group_name, workspace_name):
        try:
            raise HttpResponseError(message="HttpResponseError")
        except Exception as e:
            ex = e
        error_category, error_type, error_target, error_message, error_detail = _ErrorInfo.get_error_info(ex)
        assert error_category == ErrorCategory.SYSTEM_ERROR
        assert error_type == "HttpResponseError"
        assert error_target == ErrorTarget.RUNTIME
        assert error_message == ""
        assert error_detail == ""

    @pytest.mark.parametrize(
        "status_code, expected_error_category",
        [
            (203, ErrorCategory.SYSTEM_ERROR),
            (304, ErrorCategory.SYSTEM_ERROR),
            (400, ErrorCategory.SYSTEM_ERROR),
            (401, ErrorCategory.SYSTEM_ERROR),
            (429, ErrorCategory.SYSTEM_ERROR),
            (500, ErrorCategory.SYSTEM_ERROR),
        ],
    )
    def test_error_category_with_status_code(self, status_code, expected_error_category):
        try:
            raise Exception()
        except Exception as e:
            e.status_code = status_code
            ex = e
        error_category, error_type, error_target, error_message, error_detail = _ErrorInfo.get_error_info(ex)
        assert error_category == expected_error_category
        assert error_type == "Exception"
        assert error_target == ErrorTarget.RUNTIME
        assert error_message == ""
        assert error_detail == ""

    def test_error_category_with_inner_error1(self):
        ex = None
        try:
            try:
                FlowValidator._validate_aggregation_inputs({}, {"input1": "value1"})
            except Exception as e:
                raise UserErrorException("FlowValidator._validate_aggregation_inputs failed") from e
        except Exception as e:
            ex = e
        error_category, error_type, error_target, error_message, error_detail = _ErrorInfo.get_error_info(ex)
        assert error_category == ErrorCategory.USER_ERROR
        assert error_type == "InvalidAggregationInput"
        assert error_target == ErrorTarget.RUNTIME
        assert error_message == ""
        assert is_matching(
            "The above exception was the direct cause of the following exception:\n"
            "promptflow.executor.flow_validator, line 311, raise InvalidAggregationInput(\n",
            error_detail,
        )

        ex = None
        try:
            try:
                FlowValidator._validate_aggregation_inputs({}, {"input1": "value1"})
            except Exception as e:
                raise UserErrorException(message=str(e), error=e)
        except Exception as e:
            ex = e
        error_category, error_type, error_target, error_message, error_detail = _ErrorInfo.get_error_info(ex)
        assert error_category == ErrorCategory.USER_ERROR
        assert error_type == "InvalidAggregationInput"
        assert error_target == ErrorTarget.RUNTIME
        assert error_message == ""
        assert is_matching(
            "The above exception was the direct cause of the following exception:\n"
            "promptflow.executor.flow_validator, line 311, raise InvalidAggregationInput(\n",
            error_detail,
        )

    def test_error_category_with_inner_error2(self):
        ex = None
        try:
            try:
                FlowValidator._validate_aggregation_inputs({}, {"input1": "value1"})
            except Exception as e:
                raise Exception("FlowValidator._validate_aggregation_inputs failed") from e
        except Exception as e:
            ex = e
        error_category, error_type, error_target, error_message, error_detail = _ErrorInfo.get_error_info(ex)
        assert error_category == ErrorCategory.SYSTEM_ERROR
        assert error_type == "Exception"
        assert error_target == ErrorTarget.RUNTIME
        assert error_message == ""
        assert is_matching(
            "The above exception was the direct cause of the following exception:\n"
            "promptflow.executor.flow_validator, line 311, raise InvalidAggregationInput(\n",
            error_detail,
        )

    def test_error_category_with_inner_error3(self, pf):
        ex = None
        try:
            try:
                pf.run("./exceptions/flows")
            except Exception as e:
                raise Exception("pf run failed") from e
        except Exception as e:
            ex = e
        error_category, error_type, error_target, error_message, error_detail = _ErrorInfo.get_error_info(ex)
        assert error_category == ErrorCategory.SYSTEM_ERROR
        assert error_type == "Exception"
        assert error_target == ErrorTarget.RUNTIME
        assert error_message == ""
        assert is_matching(
            'The above exception was the direct cause of the following exception:\n'
            'promptflow._sdk._pf_client, line 119, raise FileNotFoundError(f"flow path {flow} does not exist")\n',
            error_detail,
        )

    def test_error_target_with_sdk(self, pf):
        ex = None
        try:
            pf.run("./exceptions/flows")
        except Exception as e:
            ex = e
        error_category, error_type, error_target, error_message, error_detail = _ErrorInfo.get_error_info(ex)
        assert error_category == ErrorCategory.SYSTEM_ERROR
        assert error_type == "FileNotFoundError"
        assert error_target == ErrorTarget.CONTROL_PLANE_SDK
        assert error_message == ""
        assert is_matching(
            "promptflow._sdk._pf_client, " "line 120, "
            'raise FileNotFoundError(f"flow path {flow} does not exist")\n',
            error_detail,
        )

    def test_error_target_with_executor(self):
        try:
            msg_format = (
                "Invalid node definitions found in the flow graph. Non-aggregation node '{invalid_reference}' "
                "cannot be referenced in the activate config of the aggregation node '{node_name}'. Please "
                "review and rectify the node reference."
            )
            raise InvalidNodeReference(message_format=msg_format, invalid_reference=None, node_name="node_name")
        except Exception as e:
            ex = e
        error_category, error_type, error_target, error_message, error_detail = _ErrorInfo.get_error_info(ex)
        assert error_category == ErrorCategory.USER_ERROR
        assert error_type == "InvalidNodeReference"
        assert error_target == ErrorTarget.EXECUTOR
        assert error_message == (
            "Invalid node definitions found in the flow graph. Non-aggregation node '{invalid_reference}' "
            "cannot be referenced in the activate config of the aggregation node '{node_name}'. Please "
            "review and rectify the node reference."
        )
        assert error_detail == ""

    def test_module_name_in_error_target_map(self):
        import importlib

        module_target_map = _ErrorInfo._module_target_map()
        for module_name in module_target_map.keys():
            module = importlib.import_module(module_name)
            assert module.__name__ == module_name

