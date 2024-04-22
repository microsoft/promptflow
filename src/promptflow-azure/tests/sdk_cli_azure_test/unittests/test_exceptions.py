# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import re
from pathlib import Path

import pytest
from azure.core.exceptions import HttpResponseError

from promptflow._sdk._orm import RunInfo
from promptflow.exceptions import ErrorCategory, ErrorTarget, UserErrorException, _ErrorInfo
from promptflow.executor import FlowValidator
from promptflow.executor._errors import InvalidNodeReference


def is_match_error_detail(expected_info, actual_info):
    expected_info = re.sub(r"line \d+", r"", expected_info).replace("\n", "").replace(" ", "")
    actual_info = re.sub(r"line \d+", r"", actual_info).replace("\n", "").replace(" ", "")

    return expected_info == actual_info


@pytest.mark.unittest
class TestExceptions:
    def test_error_category_with_user_error(self, pf):
        ex = None
        try:
            RunInfo.get("run_name")
        except Exception as e:
            ex = e
        error_category, error_type, error_target, error_message, error_detail = _ErrorInfo.get_error_info(ex)
        assert error_category == "UserError"
        assert error_type == "RunNotFoundError"
        assert error_target == "ControlPlaneSDK"
        assert error_message == ""
        assert is_match_error_detail(
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
        assert error_category == "SystemError"
        assert error_type == "InvalidAggregationInput"
        assert error_target == "Executor"
        assert error_message == (
            "The input for aggregation is incorrect. "
            "The value for aggregated reference input '{input_key}' should be a list, "
            "but received {value_type}. "
            "Please adjust the input value to match the expected format."
        )
        assert is_match_error_detail(
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
        assert (
            error_target == ErrorTarget.EXECUTOR
        )  # Default target is EXECUTOR due to the HttpResponseError has no target.
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
        assert error_target == ErrorTarget.EXECUTOR  # Default target is EXECUTOR due to the Exception has no target.
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
        assert (
            error_target == ErrorTarget.EXECUTOR
        )  # Default target is EXECUTOR due to the UserErrorException has no target.
        assert error_message == ""
        assert is_match_error_detail(
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
        assert (
            error_target == ErrorTarget.EXECUTOR
        )  # Default target is EXECUTOR due to the UserErrorException has no target.
        assert error_message == ""
        assert is_match_error_detail(
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
        assert error_target == ErrorTarget.EXECUTOR  # Default target is EXECUTOR due to the Exception has no target.
        assert error_message == ""
        assert is_match_error_detail(
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
        assert error_target == ErrorTarget.EXECUTOR  # Default target is EXECUTOR due to the Exception has no target.
        assert error_message == ""
        assert is_match_error_detail(
            "The above exception was the direct cause of the following exception:\n"
            "promptflow.azure._pf_client, line 260, "
            "return self.runs.create_or_update(run=run, **kwargs)\n"
            "promptflow._sdk._telemetry.activity, line 245, return f(self, *args, **kwargs)\n"
            "promptflow.azure.operations._run_operations, line 153, "
            "run._validate_for_run_create_operation()\n"
            "promptflow._sdk.entities._run, line 640, raise UserErrorException(\n",
            error_detail,
        )

    def test_error_target_with_sdk(self, pf):
        ex = None
        try:
            pf.run("./exceptions/flows")
        except Exception as e:
            ex = e
        error_category, error_type, error_target, error_message, error_detail = _ErrorInfo.get_error_info(ex)
        assert error_category == ErrorCategory.USER_ERROR
        assert error_type == "UserErrorException"
        assert error_target == ErrorTarget.CONTROL_PLANE_SDK
        assert error_message == ""
        assert is_match_error_detail(
            "promptflow.azure._pf_client, line 260, "
            "return self.runs.create_or_update(run=run, **kwargs)\n"
            "promptflow._sdk._telemetry.activity, line 245, "
            "return f(self, *args, **kwargs)\n"
            "promptflow.azure.operations._run_operations, line 153, r"
            "un._validate_for_run_create_operation()\n"
            "promptflow._sdk.entities._run, line 640, "
            "raise UserErrorException(\n",
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

    def test_message_with_empty_privacy_info(self):
        from promptflow._cli._utils import get_secret_input

        ex = None
        try:
            get_secret_input(111)
        except Exception as e:
            ex = e
        _, _, _, error_message, _ = _ErrorInfo.get_error_info(ex)
        assert error_message == "prompt must be a str, not $int"

        try:
            get_secret_input("str", mask=11)
        except Exception as e:
            ex = e
        _, _, _, error_message, _ = _ErrorInfo.get_error_info(ex)
        assert error_message == "mask argument must be a one-character str, not $int"

    def test_message_with_privacy_info_filter(self):
        from promptflow._sdk._load_functions import _load_env_to_connection

        ex = None
        try:
            _load_env_to_connection(source="./test/test", params_override=[])
        except Exception as e:
            ex = e
        _, _, _, error_message, _ = _ErrorInfo.get_error_info(ex)
        assert error_message == "Please specify --name when creating connection from .env."

        try:
            _load_env_to_connection(source="./test/test", params_override=[{"name": "test"}])
        except Exception as e:
            ex = e
        _, _, _, error_message, _ = _ErrorInfo.get_error_info(ex)
        assert error_message == "File '{privacy_info}' not found."

    def test_message_with_privacy_info_filter2(self):
        source = Path(__file__)
        e = ValueError(
            f"Load nothing from dotenv file {source.absolute().as_posix()!r}, "
            f"or not find file {source.absolute().as_posix()}, "
            "please make sure the file is not empty and readable."
        )
        ex = UserErrorException(str(e), error=e, privacy_info=[source.absolute().as_posix()])
        _, _, _, error_message, _ = _ErrorInfo.get_error_info(ex)
        assert error_message == (
            "Load nothing from dotenv file '{privacy_info}', "
            "or not find file {privacy_info}, "
            "please make sure the file is not empty and readable."
        )

        ex = UserErrorException(f"Load entity error: {ex}", privacy_info=[str(ex)])
        _, _, _, error_message, _ = _ErrorInfo.get_error_info(ex)
        assert error_message == "Load entity error: {privacy_info}"

        func = self.test_message_with_privacy_info_filter2
        request_id = "0000-0000-0000-0000"
        ex.status_code = 404
        ex.reason = "params error"
        ex = UserErrorException(
            f"Calling {func.__name__} failed with request id: {request_id}"
            f"Status code: {ex.status_code}"
            f"Reason: {ex.reason}"
            f"Error message: {ex.message}",
            privacy_info=[ex.reason, ex.message],
        )
        _, _, _, error_message, _ = _ErrorInfo.get_error_info(ex)
        assert error_message == (
            "Calling test_message_with_privacy_info_filter2 failed with request id: 0000-0000-0000-0000"
            "Status code: 404"
            "Reason: {privacy_info}"
            "Error message: {privacy_info}"
        )
