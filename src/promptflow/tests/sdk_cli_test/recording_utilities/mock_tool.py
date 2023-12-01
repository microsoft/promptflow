import functools
import inspect

from promptflow._core.tool import STREAMING_OPTION_PARAMETER_ATTR, ToolType

from .record_storage import RecordFileMissingException, RecordItemMissingException, RecordStorage

recording_array = ["fetch_text_content_from_url", "my_python_tool"]


def recording_array_extend(items):
    global recording_array
    recording_array.extend(items)


def recording_array_reset():
    global recording_array
    recording_array = ["fetch_text_content_from_url", "my_python_tool"]


def _prepare_input_dict(func, func_wo_partial, args, kwargs):
    if (
        func_wo_partial.__qualname__.startswith("AzureOpenAI")
        or func_wo_partial.__qualname__.startswith("OpenAI")
        or func_wo_partial.__qualname__ in recording_array
    ):
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


def mock_tool(
    func=None,
    *,
    name: str = None,
    description: str = None,
    type: str = None,
    input_settings=None,
    streaming_option_parameter=None,
    **kwargs,
):
    def tool_decorator(func):
        from promptflow.exceptions import UserErrorException

        global recording_array

        if type(func).__name__ == "partial":
            func_wo_partial = func.func
        else:
            func_wo_partial = func

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def decorated_tool(*args, **kwargs):
                from promptflow._core.tracer import Tracer

                input_dict = _prepare_input_dict(func, func_wo_partial, args, kwargs)

                if Tracer.active_instance() is None:
                    # Replay mode will direct return item from record file, same as below.
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
                    else:
                        # record mode is not enabled, just call the function
                        return func(*args, **kwargs)
                try:
                    Tracer.push_tool(func, args, kwargs)
                    if RecordStorage.is_replaying_mode():
                        return RecordStorage.get_instance().get_record(input_dict)
                    elif RecordStorage.is_recording_mode():
                        try:
                            output = RecordStorage.get_instance().get_record(input_dict)
                        except (RecordItemMissingException, RecordFileMissingException):
                            output = RecordStorage.get_instance().set_record(input_dict, await func(*args, **kwargs))
                    else:
                        output = await func(*args, **kwargs)
                    return Tracer.pop(output)
                except Exception as e:
                    Tracer.pop(None, e)
                    raise

            new_f = decorated_tool
        else:

            @functools.wraps(func)
            def decorated_tool(*args, **kwargs):
                from promptflow._core.tracer import Tracer

                input_dict = _prepare_input_dict(func, func_wo_partial, args, kwargs)

                if Tracer.active_instance() is None:
                    if RecordStorage.is_replaying_mode():
                        return RecordStorage.get_instance().get_record(input_dict)
                    elif RecordStorage.is_recording_mode():
                        try:
                            obj = RecordStorage.get_instance().get_record(input_dict)
                        except (RecordItemMissingException, RecordFileMissingException):
                            obj = RecordStorage.get_instance().set_record(input_dict, func(*args, **kwargs))
                        return obj
                    else:
                        # record mode is not enabled, just call the function
                        return func(*args, **kwargs)
                try:
                    Tracer.push_tool(func, args, kwargs)
                    if RecordStorage.is_replaying_mode():
                        return RecordStorage.get_instance().get_record(input_dict)
                    elif RecordStorage.is_recording_mode():
                        try:
                            output = RecordStorage.get_instance().get_record(input_dict)
                        except (RecordItemMissingException, RecordFileMissingException):
                            output = RecordStorage.get_instance().set_record(input_dict, func(*args, **kwargs))
                    else:
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
