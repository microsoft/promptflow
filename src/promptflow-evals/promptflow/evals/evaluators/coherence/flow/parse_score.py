from promptflow.core import tool
import numpy as np
import re

from typing import Optional


@tool
def parse_score(llm_output: Optional[str] = None):
    score = np.nan
    if llm_output:
        match = re.search(r'\d', llm_output)
        if match:
            score = float(match.group())

    return score
