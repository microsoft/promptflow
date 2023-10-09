import json
import re
from traceback import TracebackException

import pytest

from promptflow._core._errors import ToolExecutionError
from promptflow._core.operation_context import OperationContext
from promptflow._utils.exception_utils import (
    ErrorResponse,
    ExceptionPresenter,
    JsonSerializedPromptflowException,
    get_tb_next,
    infer_error_code_from_class,
    last_frame_info,
)
from promptflow.exceptions import (
    ErrorTarget,
    PromptflowException,
    SystemErrorException,
    UserErrorException,
    ValidationException,
)


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


def raise_context_exception():
    try:
        code_with_bug()
    except Exception as e:
        raise CustomizedContextException(e)


class CustomizedContextException(Exception):
    def __init__(self, inner_exception):
        self.inner_exception = inner_exception

    @property
    def message(self):
        code_with_bug()
        return "context exception"


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


TOOL_EXECUTION_ERROR_TRACEBACK = r"""Traceback \(most recent call last\):
  File ".*test_exception_utils.py", line .*, in code_with_bug
    1 / 0
ZeroDivisionError: division by zero
"""

TOOL_EXCEPTION_TRACEBACK = r"""
The above exception was the direct cause of the following exception:

Traceback \(most recent call last\):
  File ".*test_exception_utils.py", line .*, in test_.*
    raise_tool_execution_error\(\)
  File ".*test_exception_utils.py", line .*, in raise_tool_execution_error
    raise ToolExecutionError\(node_name="MyTool"\) from e
"""

TOOL_EXCEPTION_INNER_TRACEBACK = r"""Traceback \(most recent call last\):
  File ".*test_exception_utils.py", line .*, in raise_tool_execution_error
    code_with_bug\(\)
  File ".*test_exception_utils.py", line .*, in code_with_bug
    1 / 0
"""

GENERAL_EXCEPTION_TRACEBACK = r"""
The above exception was the direct cause of the following exception:

Traceback \(most recent call last\):
  File ".*test_exception_utils.py", line .*, in test_debug_info_for_general_exception
    raise_general_exception\(\)
  File ".*test_exception_utils.py", line .*, in raise_general_exception
    raise CustomizedException\("General exception"\) from e
"""

GENERAL_EXCEPTION_INNER_TRACEBACK = r"""Traceback \(most recent call last\):
  File ".*test_exception_utils.py", line .*, in raise_general_exception
    code_with_bug\(\)
  File ".*test_exception_utils.py", line .*, in code_with_bug
    1 / 0
"""

CONTEXT_EXCEPTION_TRACEBACK = r"""
During handling of the above exception, another exception occurred:

Traceback \(most recent call last\):
  File ".*test_exception_utils.py", line .*, in test_debug_info_for_context_exception
    raise_context_exception\(\)
  File ".*test_exception_utils.py", line .*, in raise_context_exception
    raise CustomizedContextException\(e\)
"""

CONTEXT_EXCEPTION_INNER_TRACEBACK = r"""Traceback \(most recent call last\):
  File ".*test_exception_utils.py", line .*, in raise_context_exception
    code_with_bug\(\)
  File ".*test_exception_utils.py", line .*, in code_with_bug
    1 / 0
"""


@pytest.mark.unittest
class TestExceptionUtilsCommonMethod:
    def test_get_tb_next(self):
        with pytest.raises(ToolExecutionError) as e:
            raise_tool_execution_error()
        tb_next = get_tb_next(e.value.__traceback__, 3)
        te = TracebackException(type(e.value), e.value, tb_next)
        formatted_tb = "".join(te.format())
        assert re.match(TOOL_EXCEPTION_INNER_TRACEBACK, formatted_tb)

    def test_last_frame_info(self):
        with pytest.raises(ToolExecutionError) as e:
            raise_tool_execution_error()
        frame_info = last_frame_info(e.value)
        assert "test_exception_utils.py" in frame_info.get("filename")
        assert frame_info.get("lineno") > 0
        assert frame_info.get("name") == "raise_tool_execution_error"
        assert last_frame_info(None) == {}

    @pytest.mark.parametrize(
        "error_class, expected_error_code",
        [
            (UserErrorException, "UserError"),
            (SystemErrorException, "SystemError"),
            (ValidationException, "ValidationError"),
            (ToolExecutionError, "ToolExecutionError"),
            (ValueError, "ValueError"),
        ],
    )
    def test_infer_error_code_from_class(self, error_class, expected_error_code):
        assert infer_error_code_from_class(error_class) == expected_error_code


@pytest.mark.unittest
class TestExceptionPresenter:
    def test_debug_info(self):
        # Test ToolExecutionError
        with pytest.raises(ToolExecutionError) as e:
            raise_tool_execution_error()

        presenter = ExceptionPresenter.create(e.value)
        debug_info = presenter.debug_info
        assert debug_info["type"] == "ToolExecutionError"
        assert re.match(TOOL_EXCEPTION_TRACEBACK, debug_info["stackTrace"])

        inner_exception = debug_info["innerException"]
        assert inner_exception["type"] == "ZeroDivisionError"
        assert re.match(TOOL_EXCEPTION_INNER_TRACEBACK, inner_exception["stackTrace"])

    def test_debug_info_for_context_exception(self):
        with pytest.raises(CustomizedContextException) as e:
            raise_context_exception()
        presenter = ExceptionPresenter.create(e.value)
        debug_info = presenter.debug_info
        assert debug_info["type"] == "CustomizedContextException"
        assert re.match(CONTEXT_EXCEPTION_TRACEBACK, debug_info["stackTrace"])

        inner_exception = debug_info["innerException"]
        assert inner_exception["type"] == "ZeroDivisionError"
        assert re.match(CONTEXT_EXCEPTION_INNER_TRACEBACK, inner_exception["stackTrace"])

    def test_debug_info_for_general_exception(self):
        # Test General Exception
        with pytest.raises(CustomizedException) as e:
            raise_general_exception()

        presenter = ExceptionPresenter.create(e.value)
        debug_info = presenter.debug_info
        assert debug_info["type"] == "CustomizedException"
        assert re.match(GENERAL_EXCEPTION_TRACEBACK, debug_info["stackTrace"])

        inner_exception = debug_info["innerException"]
        assert inner_exception["type"] == "ZeroDivisionError"
        assert re.match(GENERAL_EXCEPTION_INNER_TRACEBACK, inner_exception["stackTrace"])

    def test_to_dict_for_general_exception(self):
        with pytest.raises(CustomizedException) as e:
            raise_general_exception()

        presenter = ExceptionPresenter.create(e.value)
        dct = presenter.to_dict(include_debug_info=True)
        assert "debugInfo" in dct
        dct.pop("debugInfo")
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

        presenter = ExceptionPresenter.create(e.value)
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

        presenter = ExceptionPresenter.create(e.value)
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

        presenter = ExceptionPresenter.create(e.value)
        assert re.search(TOOL_EXCEPTION_INNER_TRACEBACK, presenter.formatted_traceback)
        assert re.search(TOOL_EXCEPTION_TRACEBACK, presenter.formatted_traceback)
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

    @pytest.mark.parametrize(
        "raise_exception_func, error_class, expected_error_codes",
        [
            (raise_general_exception, CustomizedException, ["SystemError", "CustomizedException"]),
            (raise_tool_execution_error, ToolExecutionError, ["UserError", "ToolExecutionError"]),
            (raise_promptflow_exception, PromptflowException, ["SystemError", "ZeroDivisionError"]),
            (raise_promptflow_exception_without_inner_exception, PromptflowException, ["SystemError"]),
        ],
    )
    def test_error_codes(self, raise_exception_func, error_class, expected_error_codes):
        with pytest.raises(error_class) as e:
            raise_exception_func()

        presenter = ExceptionPresenter.create(e.value)
        assert presenter.error_codes == expected_error_codes


@pytest.mark.unittest
class TestErrorResponse:
    def test_from_error_dict(self):
        error_dict = {
            "code": "UserError",
            "message": "Flow run failed.",
        }
        response = ErrorResponse.from_error_dict(error_dict)
        assert response.response_code == "400"
        assert response.error_codes == ["UserError"]
        assert response.message == "Flow run failed."
        response_dct = response.to_dict()
        assert response_dct["time"] is not None
        response_dct.pop("time")
        component_name = response_dct.pop("componentName", None)
        assert component_name == OperationContext.get_instance().get_user_agent()
        assert "promptflow" in component_name
        assert response_dct == {
            "error": {
                "code": "UserError",
                "message": "Flow run failed.",
            },
            "correlation": None,
            "environment": None,
            "location": None,
        }

    def test_to_simplied_dict(self):
        with pytest.raises(CustomizedException) as e:
            raise_general_exception()
        error_response = ErrorResponse.from_exception(e.value)
        assert error_response.to_simplified_dict() == {
            "error": {
                "code": "SystemError",
                "message": "General exception",
            }
        }

    def test_from_exception(self):
        with pytest.raises(CustomizedException) as e:
            raise_general_exception()

        response = ErrorResponse.from_exception(e.value).to_dict()
        assert response["time"] is not None
        response.pop("time")
        component_name = response.pop("componentName", None)
        assert component_name == OperationContext.get_instance().get_user_agent()
        assert "promptflow" in component_name
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

    @pytest.mark.parametrize(
        "error_dict, expected_additional_info",
        [
            ({"code": "UserError"}, {}),
            (
                {
                    "code": "UserError",
                    "additionalInfo": [
                        {
                            "type": "test_additional_info",
                            "info": "This is additional info for testing.",
                        },
                        "not_dict",
                        {
                            "type": "empty_info",
                        },
                        {
                            "info": "Empty type",
                        },
                        {
                            "test": "Invalid additional info",
                        },
                    ],
                },
                {"test_additional_info": "This is additional info for testing."},
            ),
        ],
    )
    def test_additional_info(self, error_dict, expected_additional_info):
        error_response = ErrorResponse.from_error_dict(error_dict)
        assert error_response.additional_info == expected_additional_info
        assert all(error_response.get_additional_info(key) == value for key, value in expected_additional_info.items())

    @pytest.mark.parametrize(
        "raise_exception_func, error_class",
        [
            (raise_general_exception, CustomizedException),
            (raise_tool_execution_error, ToolExecutionError),
        ],
    )
    def test_get_user_execution_error_info(self, raise_exception_func, error_class):
        with pytest.raises(error_class) as e:
            raise_exception_func()

        error_repsonse = ErrorResponse.from_exception(e.value)
        actual_error_info = error_repsonse.get_user_execution_error_info()
        self.assert_user_execution_error_info(e.value, actual_error_info)

    def assert_user_execution_error_info(self, exception, error_info):
        if isinstance(exception, ToolExecutionError):
            assert error_info["type"] == "ZeroDivisionError"
            assert error_info["message"] == "division by zero"
            assert error_info["filename"].endswith("test_exception_utils.py")
            assert error_info["lineno"] > 0
            assert error_info["name"] == "code_with_bug"
            assert re.match(TOOL_EXECUTION_ERROR_TRACEBACK, error_info["traceback"])
        else:
            assert error_info == {}


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

    def test_reference_code(self):
        with pytest.raises(ToolExecutionError) as e:
            raise_tool_execution_error()

        e = e.value
        assert e.reference_code == ErrorTarget.TOOL
        module = "promptflow_vectordb.tool.faiss_index_loopup"
        e.module = module
        assert e.reference_code == f"{ErrorTarget.TOOL}/{module}"

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
        assert isinstance(inner_exception, ValueError)
        assert str(inner_exception) == "bad number"
        assert str(e.value) == "test"

    def test_tool_execution_error(self):
        with pytest.raises(ToolExecutionError) as e:
            raise_tool_execution_error()

        inner_exception = e.value.inner_exception
        assert isinstance(inner_exception, ZeroDivisionError)
        assert str(inner_exception) == "division by zero"
        assert e.value.message == "Execution failure in 'MyTool': (ZeroDivisionError) division by zero"

        last_frame_info = e.value.tool_last_frame_info
        assert "test_exception_utils.py" in last_frame_info.get("filename")
        assert last_frame_info.get("lineno") > 0
        assert last_frame_info.get("name") == "code_with_bug"

        assert re.match(TOOL_EXECUTION_ERROR_TRACEBACK, e.value.tool_traceback)

    def test_code_hierarchy(self):
        with pytest.raises(ToolExecutionError) as e:
            raise_tool_execution_error()

        e = e.value
        assert e.error_codes == ["UserError", "ToolExecutionError"]

        assert ExceptionPresenter.create(e).error_code_recursed == {
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
        presenter = ExceptionPresenter.create(e)
        assert presenter.debug_info["type"] == "ToolExecutionError"
        assert re.match(TOOL_EXCEPTION_TRACEBACK, presenter.debug_info["stackTrace"])

        inner_exception = presenter.debug_info["innerException"]
        assert inner_exception["type"] == "ZeroDivisionError"
        assert re.match(TOOL_EXCEPTION_INNER_TRACEBACK, inner_exception["stackTrace"])

    def test_additional_info(self):
        with pytest.raises(ToolExecutionError) as e:
            raise_tool_execution_error()

        additional_info = ExceptionPresenter.create(e.value).to_dict().get("additionalInfo")
        assert len(additional_info) == 1

        info_0 = additional_info[0]
        assert info_0["type"] == "ToolExecutionErrorDetails"
        info_0_value = info_0["info"]
        assert info_0_value.get("type") == "ZeroDivisionError"
        assert info_0_value.get("message") == "division by zero"
        assert re.match(r".*test_exception_utils.py", info_0_value["filename"])
        assert info_0_value.get("lineno") > 0
        assert info_0_value.get("name") == "code_with_bug"
        assert re.match(TOOL_EXECUTION_ERROR_TRACEBACK, info_0_value.get("traceback"))

    def test_additional_info_for_empty_inner_error(self):
        ex = ToolExecutionError(node_name="Node1")
        dct = ExceptionPresenter.create(ex).to_dict()
        additional_info = dct.get("additionalInfo")
        assert additional_info is None

    def test_additional_info_for_empty_case(self):
        with pytest.raises(UserErrorException) as e:
            raise_user_error()

        dct = ExceptionPresenter.create(e.value).to_dict()
        additional_info = dct.get("additionalInfo")
        assert additional_info is None

    @pytest.mark.parametrize("include_debug_info", [True, False])
    def test_to_dict_turning_on_or_off_debug_info(self, include_debug_info):
        with pytest.raises(ToolExecutionError) as e:
            raise_tool_execution_error()

        e = e.value
        result = ExceptionPresenter.create(e).to_dict(include_debug_info=include_debug_info)

        if include_debug_info:
            assert "debugInfo" in result
        else:
            assert "debugInfo" not in result

    def test_to_dict(self):
        with pytest.raises(ToolExecutionError) as e:
            raise_tool_execution_error()

        e = e.value
        # We do not check include_debug_info=True since the traceback already checked in other cases
        result = ExceptionPresenter.create(e).to_dict(include_debug_info=False)

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
        result = ExceptionPresenter.create(e).to_dict(include_debug_info=False)

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

        exception_dict = ExceptionPresenter.create(e.value).to_dict(include_debug_info=True)
        message = json.dumps(exception_dict)
        exception = JsonSerializedPromptflowException(message=message)
        assert str(exception) == message
        json_serialized_exception_dict = ExceptionPresenter.create(exception).to_dict(
            include_debug_info=include_debug_info
        )
        error_dict = exception.to_dict(include_debug_info=include_debug_info)
        assert error_dict == json_serialized_exception_dict

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
