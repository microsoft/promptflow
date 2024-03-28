from promptflow.core import tool
from divider import Divider
from typing import List


@tool
def combine_code(divided: List[str]):
    code = Divider.combine(divided)
    return code
