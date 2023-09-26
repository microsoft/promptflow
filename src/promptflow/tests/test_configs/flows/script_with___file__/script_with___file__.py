from pathlib import Path

from promptflow import tool


print(f"The script is {__file__}")
assert Path(__file__).is_absolute(), f"__file__ should be absolute path, got {__file__}"


@tool
def my_python_tool(input1: str) -> str:
    from pathlib import Path
    assert Path(__file__).name == "script_with___file__.py"
    print(f"Prompt: {input1} {__file__}")
    return f"Prompt: {input1} {__file__}"
