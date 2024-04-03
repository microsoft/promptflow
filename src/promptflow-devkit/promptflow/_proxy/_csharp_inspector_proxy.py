import json
import re
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import pydash

from promptflow._constants import FlowEntryRegex
from promptflow._core._errors import UnexpectedError
from promptflow._sdk._constants import ALL_CONNECTION_TYPES, FLOW_TOOLS_JSON, PROMPT_FLOW_DIR_NAME
from promptflow._utils.flow_utils import read_json_content
from promptflow._utils.yaml_utils import load_yaml

from ._base_inspector_proxy import AbstractInspectorProxy

EXECUTOR_SERVICE_DLL = "Promptflow.dll"


class CSharpInspectorProxy(AbstractInspectorProxy):
    def __init__(self):
        super().__init__()

    def get_used_connection_names(
        self, flow_file: Path, working_dir: Path, environment_variables_overrides: Dict[str, str] = None
    ) -> List[str]:
        # TODO: support environment_variables_overrides
        flow_tools_json_path = working_dir / PROMPT_FLOW_DIR_NAME / FLOW_TOOLS_JSON
        tools_meta = read_json_content(flow_tools_json_path, "meta of tools")
        flow_dag = load_yaml(flow_file)

        connection_inputs = defaultdict(set)
        for package_id, package_meta in tools_meta.get("package", {}).items():
            for tool_input_key, tool_input_meta in package_meta.get("inputs", {}).items():
                if ALL_CONNECTION_TYPES.intersection(set(tool_input_meta.get("type"))):
                    connection_inputs[package_id].add(tool_input_key)

        connection_names = set()
        # TODO: we assume that all variants are resolved here
        # TODO: only literal connection inputs are supported
        # TODO: check whether we should ask for a specific function in csharp-core
        for node in flow_dag.get("nodes", []):
            package_id = pydash.get(node, "source.tool")
            if package_id in connection_inputs:
                for connection_input in connection_inputs[package_id]:
                    connection_name = pydash.get(node, f"inputs.{connection_input}")
                    if connection_name and not re.match(r"\${.*}", connection_name):
                        connection_names.add(connection_name)
        return list(connection_names)

    def is_flex_flow_entry(self, entry: str) -> bool:
        """Check if the flow is a flex flow entry."""
        return isinstance(entry, str) and re.match(FlowEntryRegex.CSharp, entry)

    def get_entry_meta(
        self,
        entry: str,
        working_dir: Path,
        **kwargs,
    ) -> Dict[str, str]:
        """In csharp, we need to generate metadata based on a dotnet command for now and the metadata will
        always be dumped.
        """
        # TODO: add tests for this
        with tempfile.TemporaryDirectory() as temp_dir:
            flow_file = Path(temp_dir) / "flow.dag.yaml"
            flow_file.write_text(json.dumps({"entry": entry}))

            # TODO: enable cache?
            command = [
                "dotnet",
                EXECUTOR_SERVICE_DLL,
                "--flow_meta",
                "--yaml_path",
                flow_file.absolute().as_posix(),
                "--assembly_folder",
                ".",
            ]
            try:
                subprocess.check_output(
                    command,
                    cwd=working_dir,
                )
            except subprocess.CalledProcessError as e:
                raise UnexpectedError(
                    message_format="Failed to generate flow meta for csharp flow.\n"
                    "Command: {command}\n"
                    "Working directory: {working_directory}\n"
                    "Return code: {return_code}\n"
                    "Output: {output}",
                    command=" ".join(command),
                    working_directory=working_dir.as_posix(),
                    return_code=e.returncode,
                    output=e.output,
                )
        return json.loads((working_dir / PROMPT_FLOW_DIR_NAME / "flow.json").read_text())
