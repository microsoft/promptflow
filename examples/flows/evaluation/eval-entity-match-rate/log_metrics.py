from promptflow import tool
from typing import List
from promptflow import log_metric

# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need


@tool
def log_metrics(match_counts: List[dict]):
    exact_match_rate = sum([m["exact_match"] for m in match_counts]) / len(match_counts)
    partial_match_rate = sum([m["partial_match"] for m in match_counts]) / len(match_counts)

    log_metric(key="exact_match_rate", value=exact_match_rate)
    log_metric(key="partial_match_rate", value=partial_match_rate)
    print("exact_match_rate: ", exact_match_rate)
    print("partial_match_rate: ", partial_match_rate)

    return {"exact_match_rate": exact_match_rate, "partial_match_rate": partial_match_rate}
