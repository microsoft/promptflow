from promptflow import tool
from divider import Divider


@tool
def combine_code(divided: list[str]):
    code = Divider.combine(divided)
    return code
