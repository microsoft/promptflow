from typing import Dict

import promptflow


@promptflow.tool
def parse_summary(summarization: Dict[str, str]) -> str:
    """get value in summary key

    Args:
        summarization (Dict[str, str]): summarization output from LLM call

    Returns:
        str: value in summary key
    """
    return summarization["summary"]
