import os
import re
from pathlib import Path
from typing import Any, Dict, List

from promptflow._constants import FlowEntryRegex
from promptflow._core.entry_meta_generator import _generate_flow_meta
from promptflow._sdk._constants import FLOW_META_JSON_GEN_TIMEOUT, PF_FLOW_META_LOAD_IN_SUBPROCESS
from promptflow._utils.flow_utils import resolve_python_entry_file

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

    def is_flex_flow_entry(self, entry: str) -> bool:
        """Check if the flow is a flex flow entry."""
        return isinstance(entry, str) and re.match(FlowEntryRegex.Python, entry)

    def get_entry_meta(
        self,
        entry: str,
        working_dir: Path,
        **kwargs,
    ) -> Dict[str, Any]:
        timeout = kwargs.get("timeout", FLOW_META_JSON_GEN_TIMEOUT)
        load_in_subprocess = os.environ.get(PF_FLOW_META_LOAD_IN_SUBPROCESS, "True").lower() == "true"

        flow_dag = {"entry": entry}
        # generate flow.json only for eager flow for now
        return _generate_flow_meta(
            flow_directory=working_dir,
            source_path=resolve_python_entry_file(entry=flow_dag.get("entry"), working_dir=working_dir),
            data=flow_dag,
            timeout=timeout,
            load_in_subprocess=load_in_subprocess,
        )

    def prepare_metadata(
        self,
        flow_file: Path,
        working_dir: Path,
        **kwargs,
    ) -> None:
        # for python, we have a runtime to gather metadata in both local and cloud, so we don't prepare anything
        # here so that people may submit the flow to cloud without local runtime
        pass
