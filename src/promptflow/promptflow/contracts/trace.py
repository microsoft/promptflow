# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from dataclasses import dataclass
from enum import Enum
from types import GeneratorType
from typing import Any, Dict, List, Optional


def replace_generators(obj):
    if isinstance(obj, dict):
        return {k: replace_generators(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [replace_generators(v) for v in obj]
    elif isinstance(obj, tuple):
        return tuple(replace_generators(v) for v in obj)
    elif isinstance(obj, Enum):
        return obj
    elif hasattr(obj, "__dict__"):
        for k, v in obj.__dict__.items():
            setattr(obj, k, replace_generators(v))
        return obj
    elif isinstance(obj, GeneratorType):
        return None
    else:
        return obj


class TraceType(str, Enum):
    """An enumeration class to represent different types of traces."""

    LLM = "LLM"
    TOOL = "Tool"
    LANGCHAIN = "LangChain"


@dataclass
class Trace:
    """A dataclass that represents a trace of a program execution.

    :param name: The name of the trace.
    :type name: str
    :param type: The type of the trace.
    :type type: ~promptflow.contracts.trace.TraceType
    :param inputs: The inputs of the trace.
    :type inputs: Dict[str, Any]
    :param output: The output of the trace, or None if not available.
    :type output: Optional[Any]
    :param start_time: The timestamp of the start time, or None if not available.
    :type start_time: Optional[float]
    :param end_time: The timestamp of the end time, or None if not available.
    :type end_time: Optional[float]
    :param error: The error message of the trace, or None if no error occurred.
    :type error: Optional[str]
    :param children: The list of child traces, or None if no children.
    :type children: Optional[List[Trace]]
    :param node_name: The node name of the trace, used for flow level trace, or None if not applicable.
    :type node_name: Optional[str]
    """

    name: str
    type: TraceType
    inputs: Dict[str, Any]
    output: Optional[Any] = None
    start_time: Optional[float] = None  # The timestamp of the start time
    end_time: Optional[float] = None  # The timestamp of the end time
    error: Optional[str] = None
    children: Optional[List["Trace"]] = None
    node_name: Optional[str] = None  # The node name of the trace, used for flow level trace

    def __getstate__(self):
        state = self.__dict__.copy()
        return replace_generators(state)
