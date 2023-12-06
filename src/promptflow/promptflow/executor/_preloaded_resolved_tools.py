from promptflow.contracts.flow import Flow
from promptflow.executor._tool_resolver import ToolResolver
from promptflow._utils.context_utils import _change_working_dir
from ._shared_vars import flow_file, connections, working_dir


class PreloadeResolvedTools:
    def __init__(self, flow_file, connections, working_dir):
        if flow_file and connections and working_dir:
            working_dir = Flow._resolve_working_dir(flow_file, working_dir)
            flow = Flow.from_yaml(flow_file, working_dir=working_dir)
            flow = flow._apply_default_node_variants()
            package_tool_keys = [node.source.tool for node in flow.nodes if node.source and node.source.tool]
            tool_resolver = ToolResolver(working_dir, connections, package_tool_keys)

            with _change_working_dir(working_dir):
                self._tools = [tool_resolver.resolve_tool_by_node(node) for node in flow.nodes]
        else:
            self._tools = None

    @property
    def tools(self):
        return self._tools


preloaded_obj = PreloadeResolvedTools(flow_file, connections, working_dir)
