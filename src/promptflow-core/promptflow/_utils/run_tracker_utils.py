# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import inspect
from copy import deepcopy

from promptflow.tracing.contracts.iterator_proxy import AsyncIteratorProxy, IteratorProxy


def _deep_copy_and_extract_items_from_generator_proxy(value: object) -> object:
    """Deep copy value, and if there is a GeneratorProxy, deepcopy the items from it.

    :param value: Any object.
    :type value: Object
    :return: Deep copied value.
    :rtype: Object
    """
    if isinstance(value, list):
        return [_deep_copy_and_extract_items_from_generator_proxy(v) for v in value]
    elif isinstance(value, dict):
        return {k: _deep_copy_and_extract_items_from_generator_proxy(v) for k, v in value.items()}
    elif isinstance(value, (IteratorProxy, AsyncIteratorProxy)):
        return deepcopy(value.items)
    elif inspect.isgenerator(value) or inspect.isasyncgen(value):
        return str(value)  # Convert generator to string to avoid deepcopy error
    return deepcopy(value)
