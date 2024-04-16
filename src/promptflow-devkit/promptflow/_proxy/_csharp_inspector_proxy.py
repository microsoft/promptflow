# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import pydash

from promptflow._constants import FlowEntryRegex
from promptflow._sdk._constants import ALL_CONNECTION_TYPES, FLOW_TOOLS_JSON, PROMPT_FLOW_DIR_NAME
from promptflow._utils.flow_utils import is_flex_flow, read_json_content
from promptflow._utils.yaml_utils import load_yaml
from promptflow.exceptions import UserErrorException

from ._base_inspector_proxy import AbstractInspectorProxy

EXECUTOR_SERVICE_DLL = "Promptflow.dll"


class CSharpInspectorProxy(AbstractInspectorProxy):
    def __init__(self):
        super().__init__()

    def get_used_connection_names(
        self, flow_file: Path, working_dir: Path, environment_variables_overrides: Dict[str, str] = None
    ) -> List[str]:
        if is_flex_flow(flow_path=flow_file):
            # in flex mode, csharp will always directly get connections from local pfs
            return []
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
        return isinstance(entry, str) and re.match(FlowEntryRegex.CSharp, entry) is not None

    def get_entry_meta(
        self,
        entry: str,
        working_dir: Path,
        **kwargs,
    ) -> Dict[str, str]:
        """In csharp, the metadata will always be dumped at the beginning of each local run."""
        target_path = working_dir / PROMPT_FLOW_DIR_NAME / "flow.json"
        if target_path.is_file():
            entry_meta = read_json_content(target_path, "flow metadata")
            for key in ["inputs", "outputs", "init"]:
                if key not in entry_meta:
                    continue
                for port_name, port in entry_meta[key].items():
                    if "type" in port and isinstance(port["type"], list) and len(port["type"]) == 1:
                        port["type"] = port["type"][0]
            entry_meta.pop("framework", None)
            return entry_meta
        raise UserErrorException("Flow metadata not found.")
