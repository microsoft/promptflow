# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class TraceType(str, Enum):
    """An enumeration of possible trace types.

    :cvar LLM: The LLM trace type.
    :cvar TOOL: The tool trace type.
    :cvar LANGCHAIN: The LangChain trace type.
    """

    LLM = "LLM"
    TOOL = "Tool"
    LANGCHAIN = "LangChain"


@dataclass
class Trace:
    """A dataclass that represents a trace of a program execution.

    :ivar name: The name of the trace.
    :vartype name: str
    :ivar type: The type of the trace.
    :vartype type: TraceType
    :ivar inputs: The inputs of the trace.
    :vartype inputs: Dict[str, Any]
    :ivar output: The output of the trace, or None if not available.
    :vartype output: Optional[Any]
    :ivar start_time: The timestamp of the start time, or None if not available.
    :vartype start_time: Optional[float]
    :ivar end_time: The timestamp of the end time, or None if not available.
    :vartype end_time: Optional[float]
    :ivar error: The error message of the trace, or None if no error occurred.
    :vartype error: Optional[str]
    :ivar children: The list of child traces, or None if no children.
    :vartype children: Optional[List[Trace]]
    :ivar node_name: The node name of the trace, used for flow level trace, or None if not applicable.
    :vartype node_name: Optional[str]
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
