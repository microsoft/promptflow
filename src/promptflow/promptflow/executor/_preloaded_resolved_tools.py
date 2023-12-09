import os
import json
from promptflow.contracts.flow import Flow
from promptflow.executor._tool_resolver import ToolResolver
from promptflow._utils.context_utils import _change_working_dir
from pathlib import Path
import psutil


def print_used_memory(event):
    pid = os.getpid()
    mem_info = psutil.virtual_memory()
    available_memory = mem_info.available / (1024 * 1024)  # in MB
    print(f"{pid}{event} - Used physical memory: {available_memory}")


class PreloadeResolvedTools:
    def __init__(self):
        flow_file = os.environ.get("FLOW_FILE")
        connections = os.environ.get("CONNECTIONS")
        working_dir = os.environ.get("WORKING_DIR")
        if flow_file and connections and working_dir:
            print_used_memory("before")

            flow_file = Path(flow_file)
            connections = json.loads(os.environ.get("CONNECTIONS"))
            working_dir = Path(working_dir)

            working_dir = Flow._resolve_working_dir(flow_file, working_dir)
            flow = Flow.from_yaml(flow_file, working_dir=working_dir)
            flow = flow._apply_default_node_variants()
            package_tool_keys = [node.source.tool for node in flow.nodes if node.source and node.source.tool]
            tool_resolver = ToolResolver(working_dir, connections, package_tool_keys)

            with _change_working_dir(working_dir):
                self._tools = [tool_resolver.resolve_tool_by_node(node) for node in flow.nodes]
            print_used_memory("after")
        else:
            self._tools = None

    @property
    def tools(self):
        return self._tools


preloaded_obj = PreloadeResolvedTools()
