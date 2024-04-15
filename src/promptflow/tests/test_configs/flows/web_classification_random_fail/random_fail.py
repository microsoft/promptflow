
from promptflow import tool
import random

# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need
@tool
def random_fail(url: str) -> str:
    if random.random() < 0.5:
        raise ValueError("Random failure")
    return url
