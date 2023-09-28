import sys

import pytest

from promptflow._core.tool_meta_generator import PythonLoadError
from promptflow.exceptions import ErrorTarget
from promptflow.executor._errors import ResolveToolError


def code_with_bug():
    1 / 0


def raise_resolve_tool_error(func, target=None, module=None):
    try:
        func()
    except Exception as e:
        if target:
            raise ResolveToolError(node_name="MyTool", target=target, module=module) from e
        raise ResolveToolError(node_name="MyTool") from e


def raise_python_load_error():
    try:
        code_with_bug()
    except Exception as e:
        raise PythonLoadError(message="Test PythonLoadError.") from e


def test_resolve_tool_error():
    with pytest.raises(ResolveToolError) as e:
        raise_resolve_tool_error(raise_python_load_error, ErrorTarget.TOOL, "__pf_main__")

    exception = e.value
    inner_exception = exception.inner_exception

    assert isinstance(inner_exception, PythonLoadError)
    assert exception.message == "Tool load failed in 'MyTool': (PythonLoadError) Test PythonLoadError."
    assert exception.additional_info == inner_exception.additional_info
    assert exception.error_codes == ["UserError", "ToolValidationError", "PythonParsingError", "PythonLoadError"]
    if (sys.version_info.major == 3) and (sys.version_info.minor >= 11):
        # Python >= 3.11 has a different error message
        exception.reference_code == "ErrorTarget.TOOL/__pf_main__"
    else:
        assert exception.reference_code == "Tool/__pf_main__"


def test_resolve_tool_error_with_none_inner():
    with pytest.raises(ResolveToolError) as e:
        raise ResolveToolError(node_name="MyTool")

    exception = e.value
    assert exception.inner_exception is None
    assert exception.message == "Tool load failed in 'MyTool'."
    assert exception.additional_info is None
    assert exception.error_codes == ["SystemError", "ResolveToolError"]
    assert exception.reference_code == "Executor"


def test_resolve_tool_error_with_no_PromptflowException_inner():
    with pytest.raises(ResolveToolError) as e:
        raise_resolve_tool_error(code_with_bug)

    exception = e.value
    assert isinstance(exception.inner_exception, ZeroDivisionError)
    assert exception.message == "Tool load failed in 'MyTool': (ZeroDivisionError) division by zero"
    assert exception.additional_info is None
    assert exception.error_codes == ["SystemError", "ZeroDivisionError"]
    assert exception.reference_code == "Executor"
