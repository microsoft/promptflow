import contextvars
from collections import defaultdict
from concurrent import futures
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Tuple

from promptflow._core.flow_execution_context import FlowExecutionContext
from promptflow._core.tools_manager import ToolsManager
from promptflow._utils.logger_utils import logger
from promptflow._utils.utils import set_context
from promptflow.contracts.flow import Flow, InputValueType, Node
from promptflow.executor.flow_parse_util import parse_value

RUN_FLOW_NODES_LINEARLY = 1
DEFAULT_CONCURRENCY_BULK = 2
DEFAULT_CONCURRENCY_FLOW = 16


class FlowNodesSceduler:
    def __init__(self, flow: Flow, tools_manager: ToolsManager) -> None:
        self.flow = flow
        self.tools_manager = tools_manager
        self.subsequent_nodes_name = {n.name: set() for n in flow.nodes}
        # Only collect nodes dependency in current run, not whole flow.
        for node in flow.nodes:
            inputs_list = [i for i in node.inputs.values()]
            if node.skip:
                inputs_list.extend([node.skip.condition, node.skip.return_value])
            for input in inputs_list:
                if input.value_type != InputValueType.NODE_REFERENCE:
                    continue
                self.subsequent_nodes_name[input.value].add(node.name)

    def execute(
        self, context: FlowExecutionContext, inputs: Dict, nodes_from_invoker: List[Node], node_concurrency: int
    ) -> Dict:
        # We may remove item from self.nodes, so make one copy.
        self.nodes_pending_execute = nodes_from_invoker.copy()
        # Limit the maximum threads to create.
        node_concurrency = min(node_concurrency, DEFAULT_CONCURRENCY_FLOW)
        logger.info(f"Start to run {len(self.nodes_pending_execute)} nodes with concurrency level {node_concurrency}.")

        self.context = context
        self.inputs = inputs
        self.dependency_count_dict = defaultdict(int)
        # Count the dependency number for each node.
        for each_node in self.nodes_pending_execute:
            for subsequent_nodes_name in self.subsequent_nodes_name[each_node.name]:
                self.dependency_count_dict[subsequent_nodes_name] += 1
        nodes_outputs = {}
        parent_context = contextvars.copy_context()
        with ThreadPoolExecutor(
            max_workers=node_concurrency, initializer=set_context, initargs=(parent_context,)
        ) as executor:
            self.future_to_node = {}
            nodes_to_exec = self._collect_nodes_to_exec()
            self._execute_nodes_and_update_dict(nodes_outputs, executor, nodes_to_exec)

            while len(self.future_to_node) > 0:
                try:
                    completed_futures, _ = futures.wait(self.future_to_node.keys(), return_when=futures.FIRST_COMPLETED)
                    finished_node_name_to_output = self._collect_outputs(completed_futures)
                    for each_future in completed_futures:
                        del self.future_to_node[each_future]
                    nodes_outputs.update(finished_node_name_to_output)
                    self._update_dependency(finished_node_name_to_output)
                    nodes_to_exec = self._collect_nodes_to_exec()
                    self._execute_nodes_and_update_dict(nodes_outputs, executor, nodes_to_exec)
                except Exception as e:
                    for unfinished_future in self.future_to_node.keys():
                        node_name = self.future_to_node[unfinished_future].name
                        logger.error(f"One node execution failed, cancel all running tasks. {node_name}.")
                        # We can't cancel running tasks here, only pending tasks could be cancelled.
                        unfinished_future.cancel()
                    # Even we raise exception here, still need to wait all running jobs finish to exit.
                    raise e
        return nodes_outputs

    def _collect_outputs(self, completed_futures):
        finished_node_name_to_output = {}
        for each_future in completed_futures:
            each_node_result = each_future.result()
            each_node = self.future_to_node[each_future]
            finished_node_name_to_output[each_node.name] = each_node_result
        return finished_node_name_to_output

    def _update_dependency(self, finished_node_name_to_output):
        for each_node_name in finished_node_name_to_output.keys():
            for subsequent_node_name in self.subsequent_nodes_name[each_node_name]:
                self.dependency_count_dict[subsequent_node_name] -= 1

    def _collect_nodes_to_exec(self):
        nodes_to_submit = [node for node in self.nodes_pending_execute if self.dependency_count_dict[node.name] == 0]
        for item in nodes_to_submit:
            self.nodes_pending_execute.remove(item)
        return nodes_to_submit

    def _execute_nodes_and_update_dict(self, nodes_outputs, executor, nodes):
        for each_node in nodes:
            future = executor.submit(self._exec_single_node_in_thread, (each_node, nodes_outputs))
            self.future_to_node[future] = each_node

    def _exec_single_node_in_thread(self, args: Tuple[Node, dict]):
        node, nodes_outputs = args
        if node.skip:
            skip_condition = parse_value(node.skip.condition, nodes_outputs, self.inputs)
            if skip_condition == node.skip.condition_value:
                return parse_value(node.skip.return_value, nodes_outputs, self.inputs)
        # We are using same run tracker and cache manager for all threads, which may not thread safe.
        # But for bulk run scenario, we've doing this for a long time, and it works well.
        context = self.context.copy()
        try:
            context.start()
            kwargs = {name: parse_value(i, nodes_outputs, self.inputs) for name, i in (node.inputs or {}).items()}
            f = self.tools_manager.get_tool(node.name)
            context.current_node = node
            result = f(**kwargs)
            context.current_node = None
            return result
        finally:
            context.end()
