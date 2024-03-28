from typing import List
from promptflow.core import tool


@tool
def cleansing(entities_str: str) -> List[str]:
    # Split, remove leading and trailing spaces/tabs/dots
    parts = entities_str.split(",")
    cleaned_parts = [part.strip(" \t.\"") for part in parts]
    entities = [part for part in cleaned_parts if len(part) > 0]
    return entities
