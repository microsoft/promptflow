import argparse
from file import File
from diff import show_diff
from load_code_tool import load_code
from promptflow import PFClient
from pathlib import Path


if __name__ == "__main__":
    current_folder = Path(__file__).absolute().parent
    parser = argparse.ArgumentParser(description="The code path of code that need to generate docstring.")
    parser.add_argument("--source", help="Path for the code file", default=current_folder / 'azure_open_ai.py')
    args = parser.parse_args()

    pf = PFClient()
    source = args.source
    flow_result = pf.test(flow=current_folder, inputs={"source": source})
    show_diff(load_code(source), flow_result['code'], File(source).filename)
