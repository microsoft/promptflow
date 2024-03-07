# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from promptflow import tool

# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need


@tool
def my_python_tool(input1: str, fail_wednesday_before: str) -> str:
    from datetime import datetime
    import pytz

    tz = pytz.timezone('Asia/Shanghai')
    hour = datetime.now(tz).hour
    minute = datetime.now(tz).minute
    hour_minute_str = f"{hour}".zfill(2) + f"{minute}".zfill(2)
    print(f"Current time: {hour_minute_str}")
    if "Wednesday" in input1:
        if hour_minute_str < fail_wednesday_before:
            raise Exception("Wednesday failure")
    return "Prompt: " + input1
