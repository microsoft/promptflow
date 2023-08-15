# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

"""Utility functions for runtime contracts"""
import re
from typing import Dict


def to_snake_case(name: str) -> str:
    """Converts a string from camelCase to snake_case"""
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def normalize_dict_keys_camel_to_snake(data: Dict):
    """Converts all keys in a dictionary from camelCase to snake_case"""
    if data is None:
        return {}
    return {to_snake_case(k): v for k, v in data.items()}
