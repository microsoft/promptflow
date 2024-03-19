import re
from collections import defaultdict
from pathlib import Path
from typing import List

import pydash

from promptflow._sdk._constants import ALL_CONNECTION_TYPES, FLOW_TOOLS_JSON, PROMPT_FLOW_DIR_NAME
from promptflow._utils.flow_utils import read_json_content
from promptflow._utils.yaml_utils import load_yaml

from ._base_inspector_proxy import AbstractInspectorProxy


class CSharpInspectorProxy(AbstractInspectorProxy):
    def __init__(self):
        super().__init__()

    def get_used_connection_names(self, flow_file: Path, working_dir: Path) -> List[str]:
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
