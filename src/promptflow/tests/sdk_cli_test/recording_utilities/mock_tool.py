from .record_storage import RecordFileMissingException, RecordItemMissingException, RecordStorage

recording_array = ["fetch_text_content_from_url", "my_python_tool"]


def recording_array_extend(items):
    global recording_array
    recording_array.extend(items)


def recording_array_reset():
    global recording_array
    recording_array = ["fetch_text_content_from_url", "my_python_tool"]


def mock_call_func(func, args, kwargs):
    global recording_array
    if type(func).__name__ == "partial":
        func_wo_partial = func.func
    else:
        func_wo_partial = func
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
        # Replay mode will direct return item from record file
        if RecordStorage.is_replaying_mode():
            obj = RecordStorage.get_instance().get_record(input_dict)
            return obj

        # Record mode will record item to record file
        if RecordStorage.is_recording_mode():
            # If already recorded, use previous result
            # If record item missing, call related functions and record result
            try:
                obj = RecordStorage.get_instance().get_record(input_dict)
            except (RecordItemMissingException, RecordFileMissingException):
                obj_original = func(*args, **kwargs)
                obj = RecordStorage.get_instance().set_record(input_dict, obj_original)
            # More exceptions should just raise
        else:
            obj = func(*args, **kwargs)
        return obj
    return func(*args, **kwargs)


async def mock_call_func_async(func, args, kwargs):
    global recording_array
    if type(func).__name__ == "partial":
        func_wo_partial = func.func
    else:
        func_wo_partial = func
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
        # Replay mode will direct return item from record file
        if RecordStorage.is_replaying_mode():
            obj = RecordStorage.get_instance().get_record(input_dict)
            return obj

        # Record mode will record item to record file
        if RecordStorage.is_recording_mode():
            # If already recorded, use previous result
            # If record item missing, call related functions and record result
            try:
                obj = RecordStorage.get_instance().get_record(input_dict)
            except (RecordItemMissingException, RecordFileMissingException):
                obj_original = await func(*args, **kwargs)
                obj = RecordStorage.get_instance().set_record(input_dict, obj_original)
            # More exceptions should just raise
        else:
            obj = await func(*args, **kwargs)
        return obj
    return await func(*args, **kwargs)
