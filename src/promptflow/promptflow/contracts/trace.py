from dataclasses import dataclass
from enum import Enum

from typing import Optional, Dict, Any, List


class TraceType(str, Enum):
    LLM = "LLM"
    TOOL = "Tool"
    LANGCHAIN = "LangChain"


@dataclass
class Trace:
    name: str
    type: TraceType
    inputs: Dict[str, Any]
    output: Optional[Any] = None
    start_time: Optional[float] = None  # The timestamp of the start time
    end_time: Optional[float] = None  # The timestamp of the end time
    error: Optional[str] = None
    children: Optional[List['Trace']] = None
    node_name: Optional[str] = None  # The node name of the trace, used for flow level trace
