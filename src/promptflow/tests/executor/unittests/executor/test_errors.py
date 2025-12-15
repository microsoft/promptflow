import builtins
import importlib
import sys

import pytest

from promptflow._core.tool_meta_generator import PythonLoadError
from promptflow.exceptions import ErrorTarget
from promptflow.executor._errors import ResolveToolError

TARGET_MODULE = "promptflow"  # e.g. "promptflow.loader"
DEPENDENCY_NAME = "promptflow._sdk._pf_client"  # e.g. "azure.identity"


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
    assert exception.error_codes == [
        "UserError",
        "ToolValidationError",
        "PythonParsingError",
        "PythonLoadError",
    ]
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


def test_missing_dependency_raises_import_error_gh_issue_4070(monkeypatch):
    """
    Ensure that when the specified dependency cannot be imported, importing
    TARGET_MODULE raises ImportError (i.e. the module doesn't silently swallow
    the failure with a bare `except Exception:`).

    Written with the help of GitHub Copilot.
    """
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        # If the attempted import matches the dependency (or a submodule), raise ImportError
        if name == DEPENDENCY_NAME or name.startswith(DEPENDENCY_NAME + "."):
            raise ImportError(f"No module named {DEPENDENCY_NAME}")
        return original_import(name, globals, locals, fromlist, level)

    # Apply the monkeypatch to make the target dependency unavailable
    monkeypatch.setattr(builtins, "__import__", fake_import)

    # Ensure a clean import (remove cached module if present)
    if TARGET_MODULE in sys.modules:
        del sys.modules[TARGET_MODULE]

    with pytest.raises(ImportError):
        importlib.import_module(TARGET_MODULE)
