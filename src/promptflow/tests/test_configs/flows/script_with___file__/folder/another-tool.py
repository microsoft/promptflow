from promptflow import tool


print(f"The script is {__file__}")


@tool
def my_python_tool(input1: str) -> str:
    from pathlib import Path

    assert Path(__file__).as_posix().endswith("folder/another-tool.py")
    assert __name__ == "__pf_main__"
    return f"Prompt: {input1} {__file__}"
