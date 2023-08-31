from promptflow import tool

import sys
from io import StringIO


@tool
def func_exe(code_snippet: str):
    if code_snippet == "JSONDecodeError" or code_snippet.startswith("Unknown Error:"):
        return code_snippet

    # Define the result variable before executing the code snippet
    old_stdout = sys.stdout
    redirected_output = sys.stdout = StringIO()

    # Execute the code snippet
    try:
        exec(code_snippet.lstrip())
    except Exception as e:
        sys.stdout = old_stdout
        return str(e)

    sys.stdout = old_stdout
    return redirected_output.getvalue().strip()


if __name__ == "__main__":
    print(func_exe("print(5+3)"))
    print(func_exe("count = 0\nfor i in range(100):\n    if i % 8 == 0:\n        count += 1\nprint(count)"))
    print(func_exe("sum = 0\ni = 0\nwhile 3**i < 100:\n    sum += 3**i\n    i += 1\nprint(sum)"))
    print(func_exe("speed_A = 80\nspeed_B = 120\ndistance = 2000\ntime = distance / (speed_A + speed_B)\nprint(time)"))
    print(func_exe("Unknown Error"))
    print(func_exe("JSONDecodeError"))
