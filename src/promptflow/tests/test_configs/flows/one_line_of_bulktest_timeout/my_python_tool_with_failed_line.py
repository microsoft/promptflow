from promptflow.core import tool
import random
import time


@tool
def my_python_tool_with_failed_line(idx: int, mod=5) -> int:
    if idx % mod == 0:
        while True:
            time.sleep(60)
    return idx
