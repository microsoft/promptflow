import re
from promptflow.core import tool


@tool
def apology(answer):
    return len(re.findall('(sorry)|(apology)|(apologies)', answer.lower()))
