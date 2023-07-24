import json
import re

import pytest

from promptflow.exceptions import (
    ErrorResponse,
    ErrorTarget,
    ExceptionPresenter,
    JsonSerializedPromptflowException,
    PromptflowException,
    SystemErrorException,
    ToolExecutionError,
    UserErrorException,
    infer_error_code_from_class,
)
from promptflow.utils.utils import get_runtime_version


def set_inner_exception_by_parameter():
    raise PromptflowException("test", error=ValueError("bad number"))


def set_inner_exception_by_raise_from():
    raise PromptflowException("test") from ValueError("bad number")


def code_with_bug():
    1 / 0


def raise_tool_execution_error():
    try:
        code_with_bug()
    except Exception as e:
        raise ToolExecutionError(node_name="MyTool") from e


def raise_exception_with_object():
    raise PromptflowException(message_format="{inner_exception}", inner_exception=Exception("exception message"))


def raise_user_error():
    try:
        code_with_bug()
    except Exception as e:
        raise UserErrorException("run failed", target=ErrorTarget.TOOL) from e


class CustomizedException(Exception):
    pass


class CustomUserError(UserErrorException):
    pass


class CustomDefaultTargetError(UserErrorException):
    def __init__(self, target=ErrorTarget.EXECUTOR, **kwargs):
        super().__init__(target=target, **kwargs)


def raise_general_exception():
    try:
        code_with_bug()
    except Exception as e:
        raise CustomizedException("General exception") from e


def raise_promptflow_exception():
    try:
        code_with_bug()
    except Exception as e:
        raise PromptflowException("Promptflow exception") from e


def raise_promptflow_exception_without_inner_exception():
    try:
        code_with_bug()
    except Exception:
        raise PromptflowException("Promptflow exception")


TOOL_EXCETION_TRACEBACK = r"""Traceback \(most recent call last\):
  File ".*test_exceptions.py", line .*, in raise_tool_execution_error
    code_with_bug\(\)
  File ".*test_exceptions.py", line .*, in code_with_bug
    1 / 0
ZeroDivisionError: division by zero

The above exception was the direct cause of the following exception:

Traceback \(most recent call last\):
  File ".*test_exceptions.py", line .*, in test_debug_info
    raise_tool_execution_error\(\)
  File ".*test_exceptions.py", line .*, in raise_tool_execution_error
    raise ToolExecutionError\(node_name="MyTool"\) from e
promptflow.exceptions.ToolExecutionError: Execution failure in 'MyTool': \(ZeroDivisionError\) division by zero"""


GENERAL_EXCEPTION_TRACEBACK = r"""Traceback \(most recent call last\):
  File ".*test_exceptions.py", line .*, in raise_general_exception
    code_with_bug\(\)
  File ".*test_exceptions.py", line .*, in code_with_bug
    1 / 0
ZeroDivisionError: division by zero

The above exception was the direct cause of the following exception:

Traceback \(most recent call last\):
  File ".*test_exceptions.py", line .*, in test_debug_info_for_general_exception
    raise_general_exception\(\)
  File ".*test_exceptions.py", line .*, in raise_general_exception
    raise CustomizedException\("General exception"\) from e
promptflow_test.unittests.test_exceptions.CustomizedException: General exception
"""


@pytest.mark.unittest
@pytest.mark.parametrize(
    "clz, expected",
    [
        (UserErrorException, "UserError"),
        (SystemErrorException, "SystemError"),
        (ToolExecutionError, "ToolExecutionError"),
        (ValueError, "ValueError"),
    ],
)
def test_infer_error_code_from_class(clz, expected):
    assert infer_error_code_from_class(clz) == expected


@pytest.mark.unittest
class TestExceptionPresenter:
    def test_debug_info(self):
        # Test ToolExecutionError
        with pytest.raises(ToolExecutionError) as e:
            raise_tool_execution_error()

        presenter = ExceptionPresenter(e.value)
        debug_info = presenter.debug_info
        assert presenter.debug_info["type"] == "ToolExecutionError"
        traceback = debug_info["stackTrace"]
        assert re.match(TOOL_EXCETION_TRACEBACK, traceback)

    def test_debug_info_for_general_exception(self):
        # Test General Exception
        with pytest.raises(CustomizedException) as e:
            raise_general_exception()

        presenter = ExceptionPresenter(e.value)
        debug_info = presenter.debug_info
        assert presenter.debug_info["type"] == "CustomizedException"
        traceback = debug_info["stackTrace"]
        assert re.match(GENERAL_EXCEPTION_TRACEBACK, traceback)

    def test_to_dict_for_general_exception(self):
        with pytest.raises(CustomizedException) as e:
            raise_general_exception()

        presenter = ExceptionPresenter(e.value)
        dct = presenter.to_dict(include_debug_info=False)
        assert dct == {
            "code": "SystemError",
            "message": "General exception",
            "messageFormat": "",
            "messageParameters": {},
            "innerError": {
                "code": "CustomizedException",
                "innerError": None,
            },
        }

    def test_to_dict_for_promptflow_exception(self):
        with pytest.raises(PromptflowException) as e:
            raise_promptflow_exception()

        presenter = ExceptionPresenter(e.value)
        dct = presenter.to_dict(include_debug_info=False)
        assert dct == {
            "code": "SystemError",
            "message": "Promptflow exception",
            "messageFormat": "",
            "messageParameters": {},
            "referenceCode": "Unknown",
            "innerError": {
                "code": "ZeroDivisionError",
                "innerError": None,
            },
        }

    def test_to_dict_for_promptflow_exception_without_inner_exception(self):
        with pytest.raises(PromptflowException) as e:
            raise_promptflow_exception_without_inner_exception()

        presenter = ExceptionPresenter(e.value)
        dct = presenter.to_dict(include_debug_info=False)
        assert dct == {
            "code": "SystemError",
            "message": "Promptflow exception",
            "messageFormat": "",
            "messageParameters": {},
            "referenceCode": "Unknown",
            "innerError": None,
        }

    def test_to_dict_for_tool_execution_error(self):
        with pytest.raises(ToolExecutionError) as e:
            raise_tool_execution_error()

        presenter = ExceptionPresenter(e.value)
        dct = presenter.to_dict(include_debug_info=False)
        assert dct.pop("additionalInfo") is not None
        assert dct == {
            "code": "UserError",
            "message": "Execution failure in 'MyTool': (ZeroDivisionError) division by zero",
            "messageFormat": "Execution failure in '{node_name}': {error_type_and_message}",
            "messageParameters": {
                "error_type_and_message": "(ZeroDivisionError) division by zero",
                "node_name": "MyTool",
            },
            "referenceCode": "Tool",
            "innerError": {
                "code": "ToolExecutionError",
                "innerError": None,
            },
        }


@pytest.mark.unittest
class TestErrorResponse:
    def test_from_error_dict(self):
        error_dict = {
            "code": "UserError",
            "message": "Flow run failed.",
        }
        response = ErrorResponse.from_error_dict(error_dict)
        assert response.response_code == "400"
        response_dct = response.to_dict()
        assert response_dct["time"] is not None
        response_dct.pop("time")
        component_name = response_dct.pop("componentName", None)
        assert component_name == f"promptflow/{get_runtime_version()}"
        assert response_dct == {
            "error": {
                "code": "UserError",
                "message": "Flow run failed.",
            },
            "correlation": None,
            "environment": None,
            "location": None,
        }

    def test_from_exception(self):
        with pytest.raises(CustomizedException) as e:
            raise_general_exception()

        response = ErrorResponse.from_exception(e.value).to_dict()
        assert response["time"] is not None
        response.pop("time")
        component_name = response.pop("componentName", None)
        assert component_name == f"promptflow/{get_runtime_version()}"
        assert response == {
            "error": {
                "code": "SystemError",
                "message": "General exception",
                "messageFormat": "",
                "messageParameters": {},
                "innerError": {
                    "code": "CustomizedException",
                    "innerError": None,
                },
            },
            "correlation": None,
            "environment": None,
            "location": None,
        }

    @pytest.mark.unittest
    @pytest.mark.parametrize(
        "input_dict, expected",
        [
            ({"code": "firstError"}, "firstError"),
            ({"code": "firstError", "innerError": {}}, "firstError"),
            ({"code": "firstError", "innerError": {"code": "secondError"}}, "firstError/secondError"),
            ({"code": None, "innerError": {"code": "secondError"}}, ""),
            # Dict doesn't have code in outmost will return empty string.
            ({"error": {"code": "firstError", "innerError": {"code": "secondError"}}}, ""),
        ],
    )
    def test_error_code_hierarchy(self, input_dict, expected):
        assert ErrorResponse.from_error_dict(input_dict).error_code_hierarchy == expected

    @pytest.mark.parametrize(
        "error_dict, expected_innermost_error_code",
        [
            (
                {
                    "code": "UserError",
                    "innerError": {
                        "code": "ToolExecutionError",
                        "innerError": None,
                    },
                },
                "ToolExecutionError",
            ),
            ({"code": "UserError", "innerError": None}, "UserError"),
            ({"message": "UserError", "innerError": None}, None),
        ],
    )
    def test_innermost_error_code_with_code(self, error_dict, expected_innermost_error_code):
        inner_error_code = ErrorResponse.from_error_dict(error_dict).innermost_error_code

        assert inner_error_code == expected_innermost_error_code


@pytest.mark.unittest
class TestExceptions:
    @pytest.mark.parametrize(
        "ex, expected_message, expected_message_format, expected_message_parameters",
        [
            (
                CustomUserError("message"),
                "message",
                "",
                {},
            ),
            (
                CustomUserError(message="message"),
                "message",
                "",
                {},
            ),
            (
                CustomUserError("message", target=ErrorTarget.TOOL),
                "message",
                "",
                {},
            ),
            (
                CustomUserError(message="message", target=ErrorTarget.TOOL),
                "message",
                "",
                {},
            ),
            (
                CustomUserError(message_format="Hello world"),
                "Hello world",
                "Hello world",
                {},
            ),
            (
                CustomUserError(message_format="Hello {name}", name="world"),
                "Hello world",
                "Hello {name}",
                {
                    "name": "world",
                },
            ),
            (
                CustomUserError(message_format="Hello {name}", name="world", not_used="whatever"),
                "Hello world",
                "Hello {name}",
                {
                    "name": "world",
                },
            ),
            (
                CustomUserError(message_format="Hello {name}", name="world", target=ErrorTarget.TOOL),
                "Hello world",
                "Hello {name}",
                {
                    "name": "world",
                },
            ),
            (
                CustomUserError(message_format="Hello {name} and {name}", name="world"),
                "Hello world and world",
                "Hello {name} and {name}",
                {
                    "name": "world",
                },
            ),
            (
                CustomUserError(message_format="Hello {name} and {name}", name="world"),
                "Hello world and world",
                "Hello {name} and {name}",
                {
                    "name": "world",
                },
            ),
            (
                CustomUserError(
                    message_format="Tool '{tool_name}' execution failed due to {error}",
                    tool_name="my tool",
                    error="bug",
                ),
                "Tool 'my tool' execution failed due to bug",
                "Tool '{tool_name}' execution failed due to {error}",
                {
                    "tool_name": "my tool",
                    "error": "bug",
                },
            ),
        ],
    )
    def test_message_and_format(self, ex, expected_message, expected_message_format, expected_message_parameters):
        with pytest.raises(CustomUserError) as exc:
            raise ex

        assert exc.value.message == expected_message
        assert exc.value.message_format == expected_message_format
        assert exc.value.message_parameters == expected_message_parameters

    @pytest.mark.parametrize(
        "ex, expected_message, exepcted_target",
        [
            (
                CustomDefaultTargetError(message="message", target=ErrorTarget.TOOL),
                "message",
                ErrorTarget.TOOL,
            ),
            (
                CustomDefaultTargetError(message="message"),
                "message",
                ErrorTarget.EXECUTOR,
            ),
        ],
    )
    def test_target_and_message(self, ex, expected_message, exepcted_target):
        with pytest.raises(CustomDefaultTargetError) as exc:
            raise ex

        assert exc.value.message == expected_message
        assert exc.value.target == exepcted_target

    @pytest.mark.parametrize(
        "func_that_raises_exception",
        [
            set_inner_exception_by_parameter,
            set_inner_exception_by_raise_from,
        ],
    )
    def test_inner_exception(self, func_that_raises_exception):
        with pytest.raises(PromptflowException) as e:
            func_that_raises_exception()

        inner_exception = e.value.inner_exception
        assert type(inner_exception) == ValueError
        assert str(inner_exception) == "bad number"
        assert str(e.value) == "test"

    def test_tool_execution_error(self):
        with pytest.raises(ToolExecutionError) as e:
            raise_tool_execution_error()

        inner_exception = e.value.inner_exception
        assert type(inner_exception) == ZeroDivisionError
        assert str(inner_exception) == "division by zero"
        assert e.value.message == "Execution failure in 'MyTool': (ZeroDivisionError) division by zero"

        last_frame_info = e.value.tool_last_frame_info
        assert "test_exceptions.py" in last_frame_info.get("filename")
        assert last_frame_info.get("lineno") > 0
        assert last_frame_info.get("name") == "code_with_bug"

        assert re.match(
            r"Traceback \(most recent call last\):\n"
            r'  File ".*test_exceptions.py", line .*, in code_with_bug\n'
            r"    1 / 0\n"
            r"ZeroDivisionError: division by zero\n",
            e.value.tool_traceback,
        )

    def test_code_hierarchy(self):
        with pytest.raises(ToolExecutionError) as e:
            raise_tool_execution_error()

        e = e.value
        assert e.error_codes == ["UserError", "ToolExecutionError"]

        assert e.error_code_recursed == {
            "code": "UserError",
            "innerError": {
                "code": "ToolExecutionError",
                "innerError": None,
            },
        }

    def test_debug_info(self):
        with pytest.raises(ToolExecutionError) as e:
            raise_tool_execution_error()

        e = e.value

        assert e.debug_info["type"] == "ToolExecutionError"
        assert re.match(TOOL_EXCETION_TRACEBACK, e.debug_info["stackTrace"])

    def test_additional_info(self):
        with pytest.raises(ToolExecutionError) as e:
            raise_tool_execution_error()

        additional_info = e.value.to_dict().get("additionalInfo")
        assert len(additional_info) == 1

        info_0 = additional_info[0]
        assert info_0["type"] == "ToolExecutionErrorDetails"
        info_0_value = info_0["info"]
        assert info_0_value.get("type") == "ZeroDivisionError"
        assert info_0_value.get("message") == "division by zero"
        assert re.match(r".*test_exceptions.py", info_0_value["filename"])
        assert info_0_value.get("lineno") > 0
        assert info_0_value.get("name") == "code_with_bug"
        assert re.match(
            r"Traceback \(most recent call last\):\n"
            r'  File ".*test_exceptions.py", line .*, in code_with_bug\n'
            r"    1 / 0\n"
            r"ZeroDivisionError: division by zero\n",
            info_0_value.get("traceback"),
        )

    def test_additional_info_for_empty_inner_error(self):
        ex = ToolExecutionError(node_name="Node1")
        dct = ex.to_dict()
        additional_info = dct.get("additionalInfo")
        assert additional_info is None

    def test_additional_info_for_empty_case(self):
        with pytest.raises(UserErrorException) as e:
            raise_user_error()

        dct = e.value.to_dict()
        additional_info = dct.get("additionalInfo")
        assert additional_info is None

    @pytest.mark.parametrize("include_debug_info", [True, False])
    def test_to_dict_turning_on_or_off_debug_info(self, include_debug_info):
        with pytest.raises(ToolExecutionError) as e:
            raise_tool_execution_error()

        e = e.value
        result = e.to_dict(include_debug_info=include_debug_info)

        if include_debug_info:
            assert "debugInfo" in result
        else:
            assert "debugInfo" not in result

    def test_to_dict(self):
        with pytest.raises(ToolExecutionError) as e:
            raise_tool_execution_error()

        e = e.value
        # We do not check include_debug_info=True since the traceback already checked in other cases
        result = e.to_dict(include_debug_info=False)

        # Wo do not check additonalInfo since it is already checked in other cases
        result.pop("additionalInfo")

        assert result == {
            "message": "Execution failure in 'MyTool': (ZeroDivisionError) division by zero",
            "messageFormat": "Execution failure in '{node_name}': {error_type_and_message}",
            "messageParameters": {
                "error_type_and_message": "(ZeroDivisionError) division by zero",
                "node_name": "MyTool",
            },
            "referenceCode": "Tool",
            "code": "UserError",
            "innerError": {
                "code": "ToolExecutionError",
                "innerError": None,
            },
        }

    def test_to_dict_object_parameter(self):
        with pytest.raises(PromptflowException) as e:
            raise_exception_with_object()

        e = e.value
        # We do not check include_debug_info=True since the traceback already checked in other cases
        result = e.to_dict(include_debug_info=False)

        # Assert message is str(exception)
        assert result == {
            "message": "exception message",
            "messageFormat": "{inner_exception}",
            "messageParameters": {"inner_exception": "exception message"},
            "referenceCode": "Unknown",
            "code": "SystemError",
            "innerError": None,
        }

    @pytest.mark.parametrize("include_debug_info", [True, False])
    def test_to_dict_for_JsonSerializedPromptflowException(self, include_debug_info):
        with pytest.raises(ToolExecutionError) as e:
            raise_tool_execution_error()

        exception_dict = e.value.to_dict(include_debug_info=True)
        message = json.dumps(exception_dict)
        exception = JsonSerializedPromptflowException(message=message)
        error_dict = exception.to_dict(include_debug_info=include_debug_info)

        if include_debug_info:
            assert "debugInfo" in error_dict
            error_dict.pop("debugInfo")

        error_dict.pop("additionalInfo")

        assert error_dict == {
            "code": "UserError",
            "message": "Execution failure in 'MyTool': (ZeroDivisionError) division by zero",
            "messageFormat": "Execution failure in '{node_name}': {error_type_and_message}",
            "messageParameters": {
                "node_name": "MyTool",
                "error_type_and_message": "(ZeroDivisionError) division by zero",
            },
            "referenceCode": "Tool",
            "innerError": {
                "code": "ToolExecutionError",
                "innerError": None,
            },
        }
