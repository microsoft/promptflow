from promptflow import tool
import sys


@tool
def print_inputs(
    text: str = None,
):
    print(f"STDOUT: {text}")
    print(f"STDERR: {text}", file=sys.stderr)
    return text
