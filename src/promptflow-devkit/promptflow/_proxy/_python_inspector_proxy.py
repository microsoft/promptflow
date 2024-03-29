import re
from pathlib import Path
from typing import Dict, List

from .._constants import FlowEntryRegex
from ._base_inspector_proxy import AbstractInspectorProxy


class PythonInspectorProxy(AbstractInspectorProxy):
    def __init__(self):
        super().__init__()

    def get_used_connection_names(
        self, flow_file: Path, working_dir: Path, environment_variables_overrides: Dict[str, str] = None
    ) -> List[str]:
        from promptflow._utils.context_utils import _change_working_dir
        from promptflow.contracts.flow import Flow as ExecutableFlow

        with _change_working_dir(working_dir):
            executable = ExecutableFlow.from_yaml(flow_file=flow_file, working_dir=working_dir)
        return executable.get_connection_names(environment_variables_overrides=environment_variables_overrides)

    @classmethod
    def is_flex_flow_entry(self, entry: str) -> bool:
        """Check if the flow is a flex flow entry."""
        return isinstance(entry, str) and re.match(FlowEntryRegex.Python, entry)
