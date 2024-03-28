from promptflow.core import tool
from divider import Divider


@tool
def divide_code(file_content: str):
    # Divide the code into several parts according to the global import/class/function.
    divided = Divider.divide_file(file_content)
    return divided
