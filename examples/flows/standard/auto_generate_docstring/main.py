import argparse
from dotenv import load_dotenv
from file import File
from diff import show_diff
from load_code_tool import load_code as load_code_tool
from divide_code_tool import divide_code as divide_code_tool
from generate_docstring_tool import generate_docstring as generate_docstring_tool
from combine_code_tool import combine_code as combine_code_tool


def load_code(code_path: str):
    return load_code_tool(code_path)


def divide_code(file_content: str):
    return divide_code_tool(file_content)


def generate_docstring(divided: list[str]):
    return generate_docstring_tool(divided)


def combine_code(divided: list[str]):
    return combine_code_tool(divided)


def execute_pipeline(*pipelines, args=None):
    for pipeline in pipelines:
        args = pipeline(args)
    return args


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="The code path of code that need to generate docstring.")
    parser.add_argument("--file", help="Path for the code file", default='./demo_code.py')
    args = parser.parse_args()

    load_dotenv()
    code_path = args.file
    res = execute_pipeline(
        load_code,
        divide_code,
        generate_docstring,
        combine_code,
        args=code_path
    )

    show_diff(load_code(code_path), res, File(code_path).filename)