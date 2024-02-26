from typing import List

from promptflow import tool


@tool
def aggregate(output_prompts: List[str]):
    from promptflow import log_metric
    log_metric(key="prompt_count", value=len(output_prompts))

    return output_prompts
