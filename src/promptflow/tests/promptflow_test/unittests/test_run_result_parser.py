from unittest.mock import patch
import pytest

from promptflow.utils.run_result_parser import RunResultParser
from promptflow.exceptions import ErrorResponse


A_SUCCEED_RUN = {
    "status": "Succeeded",
    "error": None,
}


A_FAILED_RUN = {
    "status": "Succeeded",
    "error": {
        "code": "UserError",
        "message": "Run 1 failed.",
    },
}

ANOTHER_FAILED_RUN = {
    "status": "Succeeded",
    "error": {
        "code": "UserError",
        "message": "Run 2 failed.",
    },
}


EMPTY_RESULT = {
}


NO_FLOW_RUNS_KEY = {
    "other_key": "other_value",
}


EMPTY_FLOW_RUNS_LIST = {
    "flow_runs": []
}


ONE_FLOW_RUN = {
    "flow_runs": [
        A_FAILED_RUN,
    ]
}


SUCCEED_RUN_RESULT = {
    "flow_runs": [
        A_SUCCEED_RUN,
        A_SUCCEED_RUN,
    ],
    "node_runs": [
        A_SUCCEED_RUN,
    ],
}


EXECUTION_FAILURE_RUN_RESULT = {
    "flow_runs": [
        A_FAILED_RUN,
        ANOTHER_FAILED_RUN,
    ],
    "node_runs": [
        A_FAILED_RUN,
    ],
}


SUCCEED_NODE_RUN_RESULT = {
    "node_runs": [
        A_SUCCEED_RUN,
    ],
}


FAILED_NODE_RUN_RESULT = {
    "node_runs": [
        A_FAILED_RUN,
    ],
}


NODE_RUN_RESULT_WITH_MULTIPLE_NODES = {
    "node_runs": [
        A_SUCCEED_RUN,
        A_FAILED_RUN,
    ],
}


@pytest.mark.unittest
class TestRunResultParser:

    @pytest.mark.parametrize("run_list, expected", [
        (None, None),
        ([], None),
        ([A_FAILED_RUN], "Run 1 failed."),
        ([A_FAILED_RUN, ANOTHER_FAILED_RUN], "Run 1 failed."),
        ([ANOTHER_FAILED_RUN, A_FAILED_RUN], "Run 2 failed."),
        ([A_SUCCEED_RUN, A_FAILED_RUN], "Run 1 failed."),
        ([A_SUCCEED_RUN, A_SUCCEED_RUN, A_FAILED_RUN], "Run 1 failed."),
        ([A_SUCCEED_RUN, A_FAILED_RUN, A_SUCCEED_RUN], "Run 1 failed."),
        ([A_SUCCEED_RUN, A_SUCCEED_RUN], None),
    ])
    def test_get_first_run_from_run_list(self, run_list, expected):
        parser = RunResultParser(None)
        error = parser._get_first_error_from_run_list(run_list)
        error_message = error.get("message") if error else None
        assert error_message == expected

    # Below are tests for _extract_error_from_run_result

    def test_extract_error_from_run_result_with_none(self):
        parser = RunResultParser(None)
        with pytest.raises(ValueError, match="Run result is None."):
            parser._extract_error_from_run_result()

    def test_extract_error_from_run_result_with_empty_result(self):
        parser = RunResultParser(EMPTY_RESULT)
        with pytest.raises(ValueError, match="Neither flow runs or node runs is found in the run result."):
            parser._extract_error_from_run_result()

    def test_extract_error_from_run_result_with_empty_list(self):
        parser = RunResultParser(NO_FLOW_RUNS_KEY)
        with pytest.raises(ValueError, match="Neither flow runs or node runs is found in the run result."):
            parser._extract_error_from_run_result()

    def test_extract_error_from_run_result_with_empty_flow_runs(self):
        parser = RunResultParser(EMPTY_FLOW_RUNS_LIST)
        with pytest.raises(ValueError, match="Neither flow runs or node runs is found in the run result."):
            parser._extract_error_from_run_result()

    def test_extract_error_from_run_result_with_one_flow_run(self):
        parser = RunResultParser(ONE_FLOW_RUN)
        error = parser._extract_error_from_run_result()
        assert error.get("message") == "Run 1 failed."

    def test_extract_error_from_run_result(self):
        parser = RunResultParser(SUCCEED_RUN_RESULT)
        error = parser._extract_error_from_run_result()
        assert error is None

    def test_extract_error_from_run_result_with_error(self):
        parser = RunResultParser(EXECUTION_FAILURE_RUN_RESULT)
        error = parser._extract_error_from_run_result()
        assert error.get("message") == "Run 2 failed."

    # Below are tests for get_error_response

    def test_get_error_response_with_succeed_runs(self):
        parser = RunResultParser(SUCCEED_RUN_RESULT)
        error_response = parser.get_error_response()
        assert error_response is None

    def test_get_error_response_with_node_succeed_runs(self):
        parser = RunResultParser(SUCCEED_NODE_RUN_RESULT)
        error_response = parser.get_error_response()
        assert error_response is None

    def test_get_error_response_with_failure_runs(self):
        parser = RunResultParser(EXECUTION_FAILURE_RUN_RESULT)
        error_response = parser.get_error_response()
        error = error_response["error"]
        assert error["message"] == "Run 2 failed."
        assert error["code"] == "UserError"

    def test_get_error_response_with_node_failure_runs(self):
        parser = RunResultParser(FAILED_NODE_RUN_RESULT)
        error_response = parser.get_error_response()
        error = error_response["error"]
        assert error["message"] == "Run 1 failed."
        assert error["code"] == "UserError"

    def test_get_error_response_with_exception(self):
        with patch.object(RunResultParser, "_extract_error_from_run_result", side_effect=Exception("test")):
            parser = RunResultParser(EMPTY_RESULT)
            error_response = parser.get_error_response()
            error = error_response["error"]
            assert error["message"] == "Failed to parse run result: (Exception) test"
            assert error["code"] == "SystemError"
            assert error["innerError"]["code"] == "RunResultParseError"
            assert error["referenceCode"] == "Runtime"

    def test_get_error_response_with_exception_without_mock(self):
        parser = RunResultParser(EMPTY_RESULT)
        error_response = parser.get_error_response()
        error = error_response["error"]
        expected_message = (
            "Failed to parse run result: "
            "(ValueError) Neither flow runs or node runs is found in the run result."
        )
        assert error["message"] == expected_message
        assert error["code"] == "SystemError"
        assert error["innerError"]["code"] == "RunResultParseError"
        assert error["referenceCode"] == "Runtime"

    def test_get_error_response_with_exception_and_then_failed_in_error_response_creation(self):
        with patch.object(RunResultParser, "_extract_error_from_run_result", side_effect=Exception("test")):
            with patch.object(ErrorResponse, "to_dict", side_effect=Exception("to_dict error")):
                parser = RunResultParser(EMPTY_RESULT)
                error_response = parser.get_error_response()
                assert error_response is None
