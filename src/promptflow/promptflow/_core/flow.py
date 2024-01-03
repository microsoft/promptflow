# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Callable, Optional

from promptflow._core.tool import STREAMING_OPTION_PARAMETER_ATTR
from promptflow._core.tracer import _traced
from promptflow.contracts.trace import TraceType


def flow(
    func=None,
    *,
    name: str = None,
    description: str = None,
    type: str = None,
    input_settings=None,
    streaming_option_parameter: Optional[str] = None,
    **kwargs,
) -> Callable:
    def wrapper(func: Callable) -> Callable:
        # All the tools should be traced.
        new_f = _traced(func, trace_type=TraceType.FLOW)

        new_f.__name = name
        new_f.__description = description
        new_f.__type = type
        new_f.__input_settings = input_settings
        new_f.__extra_info = kwargs
        if streaming_option_parameter and isinstance(streaming_option_parameter, str):
            setattr(new_f, STREAMING_OPTION_PARAMETER_ATTR, streaming_option_parameter)

        return new_f

    return wrapper
