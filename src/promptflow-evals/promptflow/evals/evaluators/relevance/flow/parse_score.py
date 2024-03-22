from promptflow import tool
import numpy as np
import re


@tool
def parse_score(llm_output: str = None):
    score = np.nan
    if llm_output:
        match = re.search(r'\d', llm_output)
        if match:
            score = float(match.group())
    
    return score
