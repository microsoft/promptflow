from promptflow import tool


@tool
def my_python_tool_with_failed_line(idx: int, mod) -> int:
    if idx % mod == 0:
        raise Exception("Failed")
    return idx