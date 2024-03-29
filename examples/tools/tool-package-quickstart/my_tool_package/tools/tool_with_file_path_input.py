import importlib
from pathlib import Path
from promptflow.core import tool
from promptflow.contracts.types import FilePath


@tool
def my_tool(input_file: FilePath, input_text: str) -> str:
    # customise your own code to handle and use the input_file here
    new_module = importlib.import_module(Path(input_file).stem)

    return new_module.hello(input_text)
