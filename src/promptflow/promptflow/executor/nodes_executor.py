import uuid
from datetime import datetime
from typing import Callable, Dict, Mapping


from promptflow.contracts.flow import Flow as FlowDefinition
from promptflow.contracts.flow import FlowInputAssignment, InputAssignment, Node, NodesRequest
from promptflow.contracts.run_info import FlowRunInfo
from promptflow.contracts.run_mode import RunMode
from promptflow.core import RunTracker
from promptflow.core.cache_manager import AbstractCacheManager
from promptflow.core.flow_execution_context import FlowExecutionContext
from promptflow.core.tools_manager import ToolsManager
from promptflow.exceptions import PromptflowException
from promptflow.executor.flow_executor import FlowExecutor


class NodesExecutor:
    def __init__(
        self,
        flow: FlowDefinition,
        connections: dict,
        run_tracker: RunTracker,
        cache_manager: AbstractCacheManager,
        loaded_tools: Mapping[str, Callable],
        raise_ex: bool = False,
    ):
        self._run_tracker = run_tracker
        self._cache_manager = cache_manager
        try:
            self._tools_manager = ToolsManager(loaded_tools)
            tool_to_meta = {tool.name: tool for tool in flow.tools}
            custom_tools = {
                node.name: self._tools_manager._load_custom_tool(tool_to_meta[node.tool], node.name)
                for node in flow.nodes
                if not self._tools_manager.loaded(node.name)
            }
            self._tools_manager.load_tools(custom_tools)
        except PromptflowException as e:
            # For PromptflowException, we don't wrap it, because need generate ErrorResponse by inner exception.
            # Will try to find one common way to handle this case.
            raise e
        except Exception as e:
            raise ValueError(f"Failed to load custom tools for flow due to exception:\n {e}.") from e
        for node in flow.nodes:
            self._tools_manager.assert_loaded(node.name)
        self._flow = flow
        self._raise_ex = raise_ex

    @staticmethod
    def _parse_value(i: InputAssignment, results: dict, node_inputs: dict):
        return FlowExecutor._parse_value(i, results, node_inputs)

    def exec_nodes(self, node_inputs: dict, run_mode: RunMode, node_name: str, variant_id: str = ""):
        """Execute a single node or from a certain node.
        Will not create flow run.
        """
        if run_mode != RunMode.SingleNode and run_mode != RunMode.FromNode:
            raise ValueError(f"Invalid run_mode {run_mode}")

        if node_name not in set(n.name for n in self._flow.nodes):
            raise ValueError(f"Node name {node_name} not found in flow nodes.")

        regular_nodes = [node for node in self._flow.nodes if not node.reduce]
        node_name_lst = [n.name for n in regular_nodes]

        nodes_to_run = []
        index_start = node_name_lst.index(node_name)
        if run_mode == RunMode.SingleNode:
            nodes_to_run = [regular_nodes[index_start]]
        elif run_mode == RunMode.FromNode:
            nodes_to_run = regular_nodes[index_start:]

        flow_run_id = RunMode(run_mode).name + "-" + str(uuid.uuid4())
        dummy_flow_run_info = FlowRunInfo(
            run_id=flow_run_id,
            status=None,
            error=None,
            inputs=None,
            output=None,
            metrics=None,
            request=None,
            parent_run_id=None,
            root_run_id=flow_run_id,
            source_run_id=None,
            flow_id=self._flow.id,
            start_time=datetime.now(),
            end_time=None,
            index=None,
            variant_id=variant_id,
        )

        results = {}
        node_inputs, results = self._setup_results_and_node_inputs(node_inputs, results)
        flow = FlowExecutionContext(
            name=self._flow.name,
            run_tracker=self._run_tracker,
            cache_manager=self._cache_manager,
            flow_run_info=dummy_flow_run_info,
            run_mode=run_mode,
        )
        flow.start()

        try:
            if run_mode == RunMode.SingleNode:
                self._exec_node(flow, nodes_to_run[0], node_inputs, results)
            elif run_mode == RunMode.FromNode:
                for node in nodes_to_run:
                    self._exec_node(flow, node, node_inputs, results)
        except Exception:
            if self._raise_ex:
                raise
        finally:
            flow.end()

    @staticmethod
    def _setup_results_and_node_inputs(node_inputs: Dict, results: Dict):
        updated_node_inputs = dict()
        for k, v in node_inputs.items():
            if FlowInputAssignment.is_flow_input(k):
                updated_k: str = FlowInputAssignment.deserialize(k).value
                # Flow input.
                updated_node_inputs.update({updated_k: v})
            else:
                # Put other node's output in result.
                node_name = NodesRequest.get_node_name_from_node_inputs_key(k)
                results.update({node_name: v})

        return updated_node_inputs, results

    def _exec_node(self, flow: FlowExecutionContext, node: Node, inputs: dict, results: dict):
        kwargs = {name: self._parse_value(i, results, inputs) for name, i in (node.inputs or {}).items()}

        f = self._tools_manager.get_tool(node.name)
        flow.current_node = node
        result = f(**kwargs)
        flow.current_node = None
        results[node.name] = result
