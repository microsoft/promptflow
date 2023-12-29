from promptflow._core.tool import STREAMING_OPTION_PARAMETER_ATTR, ToolType
from promptflow._core.tracer import _traced
from promptflow.contracts.trace import TraceType

from .record_storage import RecordFileMissingException, RecordItemMissingException, RecordStorage

# recording array is a global variable to store the function names that need to be recorded
recording_array = ["fetch_text_content_from_url", "my_python_tool"]


def recording_array_extend(items):
    global recording_array
    recording_array.extend(items)


def recording_array_reset():
    global recording_array
    recording_array = ["fetch_text_content_from_url", "my_python_tool"]


def _prepare_input_dict(func, args, kwargs):
    """Prepare input dict for record storage"""
    if func.__name__ == "partial":
        func_wo_partial = func.func
    else:
        func_wo_partial = func
    input_dict = {}
    for key in kwargs:
        input_dict[key] = kwargs[key]
    if type(func).__name__ == "partial":
        input_dict["_args"] = func.args
        for key in func.keywords:
            input_dict[key] = func.keywords[key]
    else:
        input_dict["_args"] = []
    input_dict["_func"] = func_wo_partial.__qualname__
    return input_dict


def _replace_tool_rule(func):
    """Replace tool with the following rules."""
    global recording_array
    if func.__name__ == "partial":
        func_wo_partial = func.func
    else:
        func_wo_partial = func
    if func_wo_partial.__qualname__.startswith("AzureOpenAI"):
        return True
    elif func_wo_partial.__qualname__.startswith("OpenAI"):
        return True
    elif func_wo_partial.__module__ == "promptflow.tools.aoai":
        return True
    elif func_wo_partial.__module__ == "promptflow.tools.openai_gpt4v":
        return True
    elif func_wo_partial.__module__ == "promptflow.tools.openai":
        return True
    elif func_wo_partial.__qualname__ in recording_array:
        return True
    else:
        return False


def call_func(func, args, kwargs):
    input_dict = _prepare_input_dict(func, args, kwargs)
    if RecordStorage.is_replaying_mode():
        return RecordStorage.get_instance().get_record(input_dict)
    # Record mode will record item to record file
    elif RecordStorage.is_recording_mode():
        try:
            # prevent recording the same item twice
            obj = RecordStorage.get_instance().get_record(input_dict)
        except (RecordItemMissingException, RecordFileMissingException):
            # recording the item
            obj = RecordStorage.get_instance().set_record(input_dict, func(*args, **kwargs))
    return obj


async def call_func_async(func, args, kwargs):
    input_dict = _prepare_input_dict(func, args, kwargs)
    if RecordStorage.is_replaying_mode():
        return RecordStorage.get_instance().get_record(input_dict)
    # Record mode will record item to record file
    elif RecordStorage.is_recording_mode():
        try:
            # prevent recording the same item twice
            obj = RecordStorage.get_instance().get_record(input_dict)
        except (RecordItemMissingException, RecordFileMissingException):
            # recording the item
            obj = RecordStorage.get_instance().set_record(input_dict, await func(*args, **kwargs))
    return obj


def mock_tool(original_tool):
    """
    Basically this is the original tool decorator.

    The key modification is, at every func(*args, **argv) call. There is a surrounding record/replay logic:
        if replay:
            return replay:
        elif record:
            if recorded:
                return recorded
            call func(*args, **argv) and record the result

    Actually it needn't to be such a long function, but tool decorator should not trigger a long stack trace.
    """

    def tool(
        func=None,
        *args_mock,
        name: str = None,
        description: str = None,
        type: str = None,
        input_settings=None,
        streaming_option_parameter=None,
        **kwargs_mock,
    ):
        def tool_decorator(func):
            from promptflow.exceptions import UserErrorException

            if type is not None and type not in [k.value for k in ToolType]:
                raise UserErrorException(f"Tool type {type} is not supported yet.")

            # Calls to tool functions should be traced automatically.
            new_f = _traced(func, trace_type=TraceType.TOOL)

            new_f.__original_function = func
            func.__wrapped_function = new_f
            new_f.__tool = None  # This will be set when generating the tool definition.
            new_f.__name = name
            new_f.__description = description
            new_f.__type = type
            new_f.__input_settings = input_settings
            new_f.__extra_info = kwargs_mock
            if streaming_option_parameter and isinstance(streaming_option_parameter, str):
                setattr(new_f, STREAMING_OPTION_PARAMETER_ATTR, streaming_option_parameter)

            return new_f

        # tool replacements.
        if func is not None:
            if not _replace_tool_rule(func):
                return original_tool(
                    func,
                    *args_mock,
                    name=name,
                    description=description,
                    type=type,
                    input_settings=input_settings,
                    **kwargs_mock,
                )
            return tool_decorator(func)
        return original_tool(  # no recording for @tool(name="func_name")
            func,
            *args_mock,
            name=name,
            description=description,
            type=type,
            input_settings=input_settings,
            **kwargs_mock,
        )

    return tool
