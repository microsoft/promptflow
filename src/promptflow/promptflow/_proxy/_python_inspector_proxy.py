from pathlib import Path
from typing import List

from ._base_inspector_proxy import AbstractInspectorProxy


class PythonInspectorProxy(AbstractInspectorProxy):
    def __init__(self):
        super().__init__()

    def get_used_connection_names(self, flow_file: Path, working_dir: Path) -> List[str]:
        from promptflow._utils.context_utils import _change_working_dir
        from promptflow.contracts.flow import Flow as ExecutableFlow

        with _change_working_dir(working_dir):
            executable = ExecutableFlow.from_yaml(flow_file=flow_file, working_dir=working_dir)
        return executable.get_connection_names()
