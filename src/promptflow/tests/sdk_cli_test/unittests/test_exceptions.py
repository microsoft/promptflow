# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import pytest
from promptflow._sdk._pf_client import PFClient
from promptflow.exceptions import ErrorInfo, ErrorCategory, ErrorTarget
from promptflow.executor import FlowValidator
from promptflow.executor._errors import InvalidNodeReference

FLOWS_DIR = "./tests/test_configs/flows/print_input_flow"


@pytest.mark.unittest
class TestExceptions:
    @pytest.fixture(autouse=True)
    def init(self):
        self.pf_client = PFClient()

    def test_error_category_with_sdk_error(self):
        ex = None
        try:
            self.pf_client.run("./exceptions/flows")
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
        ex = None
        try:
            from promptflow.azure import PFClient
            from azure.identity import AzureCliCredential, DefaultAzureCredential

            try:
                credential = AzureCliCredential()
            except Exception:
                credential = DefaultAzureCredential()
            PFClient(
                credential=credential,
                subscription_id="00000000-0000-0000-0000-000000000000",
                resource_group_name="00000",
                workspace_name="00000",
            )
        except Exception as e:
            ex = e
        error_category, error_type, error_target, error_message = ErrorInfo.get_error_info(ex)
        assert error_category == ErrorCategory.SystemError
        assert error_type == "ResourceNotFoundError"
        assert error_target == ErrorTarget.UNKNOWN
        assert (
            "exception msg=, exception module=promptflow.azure._pf_client, "
            "exception code=workspace = self._ml_client.workspaces.get("
            "name=self._ml_client._operation_scope.workspace_name), exception lineno="
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
        assert ("exception msg=Invalid node definitions found in the flow graph. "
                "Non-aggregation node '{invalid_reference}' cannot be referenced in the activate "
                "config of the aggregation node '{node_name}'. "
                "Please review and rectify the node reference., "
                "exception module=sdk_cli_test.unittests.test_exceptions, "
                "exception code=raise InvalidNodeReference(message_format=msg_format, "
                "invalid_reference=None, node_name=\"node_name\"), "
                "exception lineno=96") in error_message
