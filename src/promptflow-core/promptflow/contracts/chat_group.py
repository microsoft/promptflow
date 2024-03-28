from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass
from promptflow.contracts.flow import Flow


@dataclass
class ChatGroupRole:
    """This class represents the chat group role properties.

    :param flow_file: The flow file path
    :type flow_file: Path
    :param role: The role flow stands for.
    :type role: str
    :param stop_signal: The stop signal to end the chat.
    :type stop_signal: str
    :param working_dir: The flow working directory path
    :type working_dir: Optional[Path]
    :param connections: The connections used in the flow
    :type connections: Optional[dict]
    """

    flow_file: Path
    role: str
    name: str
    stop_signal: str
    working_dir: Optional[Path] = None
    connections: Optional[Dict[str, Any]] = None
    inputs_mapping: Optional[Dict[str, str]] = None
    flow: Optional[Flow] = None
