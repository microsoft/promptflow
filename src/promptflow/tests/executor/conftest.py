import functools
import inspect
from enum import Enum
from typing import Callable, Optional

import pytest
from pytest_mock import MockerFixture

from .recording_utilities import RecordStorage


class ToolType(str, Enum):
    LLM = "llm"
    PYTHON = "python"
    CSHARP = "csharp"
    PROMPT = "prompt"
    _ACTION = "action"
    CUSTOM_LLM = "custom_llm"


STREAMING_OPTION_PARAMETER_ATTR = "_streaming_option_parameter"


def mock_tool(
    func=None,
    *,
    name: str = None,
    description: str = None,
    type: str = None,
    input_settings=None,
    streaming_option_parameter: Optional[str] = None,
    **kwargs,
):
    def tool_decorator(func: Callable) -> Callable:
        from promptflow.exceptions import UserErrorException

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def decorated_tool(*args, **kwargs):
                from promptflow._core.tracer import Tracer

                # Recording mode here

                if Tracer.active_instance() is None:
                    return await func(*args, **kwargs)
                try:
                    Tracer.push_tool(func, args, kwargs)
                    output = await func(*args, **kwargs)
                    # recording quit.
                    return Tracer.pop(output)
                except Exception as e:
                    Tracer.pop(None, e)
                    raise

            new_f = decorated_tool
        else:

            @functools.wraps(func)
            def decorated_tool(*args, **kwargs):
                from promptflow._core.tracer import Tracer

                if Tracer.active_instance() is None:
                    return func(*args, **kwargs)  # Do nothing if no tracing is enabled.
                try:
                    Tracer.push_tool(func, args, kwargs)
                    output = func(*args, **kwargs)
                    return Tracer.pop(output)
                except Exception as e:
                    Tracer.pop(None, e)
                    raise

            new_f = decorated_tool

        if type is not None and type not in [k.value for k in ToolType]:
            raise UserErrorException(f"Tool type {type} is not supported yet.")

        new_f.__original_function = func
        func.__wrapped_function = new_f
        new_f.__tool = None  # This will be set when generating the tool definition.
        new_f.__name = name
        new_f.__description = description
        new_f.__type = type
        new_f.__input_settings = input_settings
        new_f.__extra_info = kwargs
        if streaming_option_parameter and isinstance(streaming_option_parameter, str):
            setattr(new_f, STREAMING_OPTION_PARAMETER_ATTR, streaming_option_parameter)

        return new_f

    # enable use decorator without "()" if all arguments are default values
    if func is not None:
        return tool_decorator(func)
    return tool_decorator


@pytest.fixture
def recording_file_override(request: pytest.FixtureRequest, mocker: MockerFixture):
    if RecordStorage.is_replaying_mode() or RecordStorage.is_recording_mode():
        file_path = "/tmp/node_cache.shelve"
        RecordStorage.get_instance(file_path)
    yield


@pytest.fixture
def recording_injection(mocker: MockerFixture, recording_file_override):
    if RecordStorage.is_replaying_mode() or RecordStorage.is_recording_mode():
        from promptflow._core.tool import tool as original_fun

        new_tool = mock_tool(original_fun)
        mocker.patch("promptflow._core.tool.tool", new_tool)
        mocker.patch("promptflow._internal.tool", new_tool)
    yield
