from promptflow import tool
import re


@tool
def parse_score(gpt_score: str):
    return float(extract_float(gpt_score))


def extract_float(s):
    match = re.search(r"[-+]?\d*\.\d+|\d+", s)
    if match:
        return float(match.group())
    else:
        return None
