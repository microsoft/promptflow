# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import copy
import functools
import inspect
import os
import uuid
from pathlib import Path
from threading import current_thread
from types import GeneratorType
from typing import AbstractSet, Any, Callable, Dict, List, Mapping, Optional, Tuple

import yaml

from promptflow._core.cache_manager import AbstractCacheManager
from promptflow._core.flow_execution_context import FlowExecutionContext
from promptflow._core.metric_logger import add_metric_logger, remove_metric_logger
from promptflow._core.openai_injector import inject_openai_api
from promptflow._core.operation_context import OperationContext
from promptflow._core.run_tracker import RunTracker
from promptflow._core.tool import ToolInvoker
from promptflow._core.tools_manager import ToolsManager
from promptflow._utils.context_utils import _change_working_dir
from promptflow._utils.logger_utils import logger
from promptflow._utils.utils import transpose
from promptflow.contracts.flow import Flow, InputAssignment, InputValueType, Node
from promptflow.contracts.run_info import FlowRunInfo, Status
from promptflow.contracts.run_mode import RunMode
from promptflow.exceptions import ErrorTarget, PromptflowException, SystemErrorException, ValidationException
from promptflow.executor import _input_assignment_parser
from promptflow.executor._errors import NodeConcurrencyNotFound
from promptflow.executor._flow_nodes_scheduler import (
    DEFAULT_CONCURRENCY_BULK,
    DEFAULT_CONCURRENCY_FLOW,
    FlowNodesScheduler,
)
from promptflow.executor._result import AggregationResult, BulkResult, LineResult
from promptflow.executor._tool_resolver import ToolResolver
from promptflow.executor.flow_validator import FlowValidator
from promptflow.executor.tool_invoker import DefaultToolInvoker
from promptflow.storage import AbstractRunStorage, DummyRunStorage

LINE_NUMBER_KEY = "line_number"  # Using the same key with portal.
LINE_TIMEOUT_SEC = 600


class FlowExecutor:
    """This class is used to execute a single flow for different inputs."""

    DEFAULT_WORKER_COUNT = 16

    def __init__(
        self,
        flow: Flow,
        connections: dict,
        run_tracker: RunTracker,
        cache_manager: AbstractCacheManager,
        loaded_tools: Mapping[str, Callable],
        *,
        worker_count=None,
        raise_ex: bool = False,
        working_dir=None,
        line_timeout_sec=LINE_TIMEOUT_SEC,
        flow_file=None,
    ):
        # Inject OpenAI API to make sure traces and headers injection works and
        # update OpenAI API configs from environment variables.
        inject_openai_api()

        self._flow = flow
        self._flow_id = flow.id or str(uuid.uuid4())
        self._connections = connections
        self._aggregation_inputs_references = self._get_aggregation_inputs_properties(flow)
        self._aggregation_nodes = {node.name for node in self._flow.nodes if node.aggregation}
        if worker_count is not None:
            self._worker_count = worker_count
        else:
            try:
                worker_count = int(os.environ.get("PF_WORKER_COUNT", self.DEFAULT_WORKER_COUNT))
                self._worker_count = worker_count
            except Exception:
                self._worker_count = self.DEFAULT_WORKER_COUNT
        if self._worker_count <= 0:
            self._worker_count = self.DEFAULT_WORKER_COUNT
        self._run_tracker = run_tracker
        self._cache_manager = cache_manager
        self._loaded_tools = loaded_tools
        self._working_dir = working_dir
        self._line_timeout_sec = line_timeout_sec
        self._flow_file = flow_file
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
        self._raise_ex = raise_ex
        self._log_interval = 60
        self._processing_idx = None
        self._completed_idx = None
        # TODO: Improve the experience about configuring node concurrency.
        self._node_concurrency = DEFAULT_CONCURRENCY_BULK

    @classmethod
    def create(
        cls,
        flow_file: Path,
        connections: dict,
        working_dir: Optional[Path] = None,
        *,
        storage: Optional[AbstractRunStorage] = None,
        raise_ex: bool = True,
        node_override: Optional[Dict[str, Dict[str, Any]]] = None,
        line_timeout_sec: int = LINE_TIMEOUT_SEC,
    ) -> "FlowExecutor":
        working_dir = Flow._resolve_working_dir(flow_file, working_dir)
        flow = Flow.from_yaml(flow_file, working_dir=working_dir, gen_tool=False)
        if node_override:
            flow = flow.apply_node_overrides(node_override)
        package_tool_keys = [node.source.tool for node in flow.nodes if node.source and node.source.tool]
        tool_resolver = ToolResolver(working_dir, connections, package_tool_keys)

        with _change_working_dir(working_dir):
            resolved_tools = [tool_resolver.resolve_tool_by_node(node) for node in flow.nodes]
        flow = Flow(
            flow.id, flow.name, [r.node for r in resolved_tools], inputs=flow.inputs, outputs=flow.outputs, tools=[]
        )
        # ensure_flow_valid including validation + resolve
        # Todo: 1) split pure validation + resovle from below method 2) provide completed validation()
        flow = FlowValidator._validate_nodes_topology(flow)
        flow.outputs = FlowValidator._ensure_outputs_valid(flow)

        if storage is None:
            storage = DummyRunStorage()
        run_tracker = RunTracker(storage)

        cache_manager = AbstractCacheManager.init_from_env()

        ToolInvoker.activate(DefaultToolInvoker())

        return FlowExecutor(
            flow=flow,
            connections=connections,
            run_tracker=run_tracker,
            cache_manager=cache_manager,
            loaded_tools={r.node.name: r.callable for r in resolved_tools},
            raise_ex=raise_ex,
            working_dir=working_dir,
            line_timeout_sec=line_timeout_sec,
            flow_file=flow_file,
        )

    @classmethod
    def load_and_exec_node(
        cls,
        flow_file: Path,
        node_name: str,
        *,
        flow_inputs: Optional[Mapping[str, Any]] = None,
        dependency_nodes_outputs: Optional[Mapping[str, Any]] = None,
        connections: Optional[dict] = None,
        working_dir: Optional[Path] = None,
        raise_ex: bool = False,
    ):
        OperationContext.get_instance().run_mode = RunMode.SingleNode.name
        dependency_nodes_outputs = dependency_nodes_outputs or {}

        # Load the node from the flow file
        working_dir = Flow._resolve_working_dir(flow_file, working_dir)
        with open(working_dir / flow_file, "r") as fin:
            flow = Flow.deserialize(yaml.safe_load(fin))
        node = flow.get_node(node_name)
        if node is None:
            raise ValueError(f"Node {node_name} not found in flow {flow_file}.")
        if not node.source or not node.type:
            raise ValueError(f"Node {node_name} is not a valid node in flow {flow_file}.")

        converted_flow_inputs_for_node = FlowValidator.convert_flow_inputs_for_node(flow, node, flow_inputs)
        package_tool_keys = [node.source.tool] if node.source and node.source.tool else []
        tool_resolver = ToolResolver(working_dir, connections, package_tool_keys)
        resolved_node = tool_resolver.resolve_tool_by_node(node)

        # Prepare callable and real inputs here

        resolved_inputs = {}
        for k, v in resolved_node.node.inputs.items():
            value = _input_assignment_parser.parse_value(v, dependency_nodes_outputs, converted_flow_inputs_for_node)
            resolved_inputs[k] = value
            if resolved_node.node.aggregation:
                # For aggregation node, we need to convert value to list.
                if (
                    v.value_type == InputValueType.FLOW_INPUT
                    or v.value_type == InputValueType.NODE_REFERENCE
                    and flow.is_normal_node(v.value)
                ):
                    resolved_inputs[k] = [value]

        # Note that the init args are only used when resolving the tool,
        # so we need to remove them from the inputs before invoking.
        resolved_inputs = {k: v for k, v in resolved_inputs.items() if k not in resolved_node.init_args}

        # TODO: Simplify the logic here
        run_tracker = RunTracker(DummyRunStorage())
        with run_tracker.node_log_manager:
            ToolInvoker.activate(DefaultToolInvoker())

            # Will generate node run in context
            context = FlowExecutionContext(
                name=flow.name,
                run_tracker=run_tracker,
                cache_manager=AbstractCacheManager.init_from_env(),
            )
            context.current_node = node
            context.start()
            try:
                resolved_node.callable(**resolved_inputs)
            except Exception:
                if raise_ex:
                    raise
            finally:
                context.end()
            node_runs = run_tracker.collect_node_runs()
            if len(node_runs) != 1:
                # Should not happen except there is bug in run_tracker or thread control.
                raise NodeResultCountNotMatch("Expecting eactly one node run.")
            return node_runs[0]

    @staticmethod
    def update_environment_variables_with_connections(connections: dict):
        from promptflow._sdk._utils import update_environment_variables_with_connections

        return update_environment_variables_with_connections(connections)

    def convert_flow_input_types(self, inputs: dict):
        return FlowValidator.resolve_flow_inputs_type(self._flow, inputs)

    def collect_run_infos(self):
        return self._run_tracker.collect_all_run_infos_as_dicts()

    @property
    def default_inputs_mapping(self):
        return {key: f"${{data.{key}}}" for key in self._flow.inputs}

    @property
    def has_aggregation_node(self):
        return len(self._aggregation_nodes) > 0

    @property
    def aggregation_nodes(self):
        return self._aggregation_nodes

    @staticmethod
    def _get_aggregation_inputs_properties(flow: Flow) -> AbstractSet[str]:
        normal_node_names = {node.name for node in flow.nodes if flow.is_normal_node(node.name)}
        properties = set()
        for node in flow.nodes:
            if node.name in normal_node_names:
                continue
            for value in node.inputs.values():
                if not value.value_type == InputValueType.NODE_REFERENCE:
                    continue
                if value.value in normal_node_names:
                    properties.add(value.serialize())
        return properties

    def _collect_lines(self, indexes: List[int], kvs: Mapping[str, List]) -> Mapping[str, List]:
        """Collect the values from the kvs according to the indexes."""
        return {k: [v[i] for i in indexes] for k, v in kvs.items()}

    def _fill_lines(self, idxes, values, nlines):
        """Fill the values into the result list according to the indexes."""
        result = [None] * nlines
        for idx, value in zip(idxes, values):
            result[idx] = value
        return result

    def _handle_line_failures(self, run_infos: List[FlowRunInfo], raise_on_line_failure: bool = False):
        failed = [i for i, r in enumerate(run_infos) if r.status == Status.Failed]
        failed_msg = None
        if len(failed) > 0:
            failed_indexes = ",".join([str(i) for i in failed])
            first_fail_exception = run_infos[failed[0]].error["message"]
            if raise_on_line_failure:
                failed_msg = "Flow run failed due to the error: " + first_fail_exception
                raise Exception(failed_msg)

            failed_msg = (
                f"{len(failed)}/{len(run_infos)} flow run failed, indexes: [{failed_indexes}],"
                f" exception of index {failed[0]}: {first_fail_exception}"
            )
            logger.error(failed_msg)

    def _exec_batch_with_threads(
        self, batch_inputs: List[dict], run_id, validate_inputs: bool = True, variant_id: str = ""
    ) -> List[LineResult]:
        nlines = len(batch_inputs)
        line_number = [
            batch_input["line_number"] for batch_input in batch_inputs if "line_number" in batch_input.keys()
        ]
        has_line_number = len(line_number) > 0
        if not has_line_number:
            line_number = [i for i in range(nlines)]

        # TODO: Such scenario only occurs in legacy scenarios, will be deprecated.
        has_duplicates = len(line_number) != len(set(line_number))
        if has_duplicates:
            line_number = [i for i in range(nlines)]

        result_list = []

        from ._line_execution_process_pool import LineExecutionProcessPool

        with LineExecutionProcessPool(
            self,
            nlines,
            run_id,
            variant_id,
            validate_inputs,
        ) as pool:
            result_list = pool.run(zip(line_number, batch_inputs))

        return sorted(result_list, key=lambda r: r.run_info.index)

    def _exec_aggregation_with_bulk_results(
        self,
        batch_inputs: List[dict],
        results: List[LineResult],
        run_id=None,
    ) -> AggregationResult:
        if not self.aggregation_nodes:
            return AggregationResult({}, {}, {})

        logger.info("Executing aggregation nodes...")

        run_infos = [r.run_info for r in results]
        succeeded = [i for i, r in enumerate(run_infos) if r.status == Status.Completed]

        succeeded_batch_inputs = [batch_inputs[i] for i in succeeded]
        resolved_succeeded_batch_inputs = [
            FlowValidator.ensure_flow_inputs_type(flow=self._flow, inputs=input) for input in succeeded_batch_inputs
        ]

        succeeded_inputs = transpose(resolved_succeeded_batch_inputs, keys=list(self._flow.inputs.keys()))

        aggregation_inputs = transpose(
            [result.aggregation_inputs for result in results],
            keys=self._aggregation_inputs_references,
        )
        succeeded_aggregation_inputs = self._collect_lines(succeeded, aggregation_inputs)
        try:
            aggr_results = self._exec_aggregation(succeeded_inputs, succeeded_aggregation_inputs, run_id)
            logger.info("Finish executing aggregation nodes.")
            return aggr_results
        except PromptflowException as e:
            # For PromptflowException, we already do classification, so throw directly.
            raise e
        except Exception as e:
            raise Exception(f"Failed to run aggregation nodes:\n {e}.") from e

    @staticmethod
    def _try_get_aggregation_input(val: InputAssignment, aggregation_inputs: dict):
        if val.value_type != InputValueType.NODE_REFERENCE:
            return val
        serialized_val = val.serialize()
        if serialized_val not in aggregation_inputs:
            return val
        return InputAssignment(value=aggregation_inputs[serialized_val])

    def get_status_summary(self, run_id: str):
        return self._run_tracker.get_status_summary(run_id)

    def exec_aggregation(
        self,
        inputs: Mapping[str, Any],
        aggregation_inputs: Mapping[str, Any],
        run_id=None,
        node_concurrency=DEFAULT_CONCURRENCY_FLOW,
    ) -> AggregationResult:
        self._node_concurrency = node_concurrency
        with self._run_tracker.node_log_manager:
            return self._exec_aggregation(inputs, aggregation_inputs, run_id)

    def _exec_aggregation(
        self,
        inputs: Mapping[str, Any],
        aggregation_inputs: Mapping[str, Any],
        run_id=None,
    ) -> AggregationResult:
        if not self._flow.has_aggregation_node:
            return AggregationResult({}, {}, {})
        run_id = run_id or str(uuid.uuid4())
        nodes = [copy.deepcopy(node) for node in self._flow.nodes if node.aggregation]
        # Update the inputs of the aggregation nodes with the aggregation inputs.
        for node in nodes:
            node.inputs = {
                k: FlowExecutor._try_get_aggregation_input(v, aggregation_inputs) for k, v in node.inputs.items()
            }

        # TODO: Use a new run tracker to avoid memory increase infinitely.
        run_tracker = self._run_tracker
        context = FlowExecutionContext(
            name=self._flow.name,
            run_tracker=run_tracker,
            cache_manager=self._cache_manager,
            run_id=run_id,
            flow_id=self._flow_id,
        )
        metrics = {}

        def _log_metric(key, value):
            metrics[key] = value

        add_metric_logger(_log_metric)
        try:
            self._submit_to_scheduler(context, inputs, nodes)
            node_run_infos = run_tracker.collect_child_node_runs(run_id)
            # Output is set as an empty dict, because the aggregation outputs story is not finalized.
            return AggregationResult({}, metrics, {run.node: run for run in node_run_infos})
        finally:
            remove_metric_logger(_log_metric)

    def exec(self, inputs: dict, node_concurency=DEFAULT_CONCURRENCY_FLOW) -> dict:
        self._node_concurrency = node_concurency
        result = self._exec(inputs)
        #  TODO: remove this line once serving directly calling self.exec_line
        self._add_line_results([result])
        return result.output or {}

    def _exec_in_thread(self, args) -> LineResult:
        inputs, run_id, line_number, variant_id, validate_inputs = args
        thread_name = current_thread().name
        self._processing_idx[line_number] = thread_name
        self._run_tracker._activate_in_context()
        results = self._exec(
            inputs, run_id=run_id, line_number=line_number, variant_id=variant_id, validate_inputs=validate_inputs
        )
        self._run_tracker._deactivate_in_context()
        self._processing_idx.pop(line_number)
        self._completed_idx[line_number] = thread_name
        return results

    def _extract_aggregation_inputs(self, nodes_outputs: dict):
        return {
            prop: self._extract_aggregation_input(nodes_outputs, prop) for prop in self._aggregation_inputs_references
        }

    def _extract_aggregation_input(self, nodes_outputs: dict, aggregation_input_property: str):
        assign = InputAssignment.deserialize(aggregation_input_property)
        return _input_assignment_parser.parse_value(assign, nodes_outputs, {})

    def exec_line(
        self,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
        variant_id: str = "",
        validate_inputs: bool = True,
        node_concurrency=DEFAULT_CONCURRENCY_FLOW,
        allow_generator_output: bool = False,
    ) -> LineResult:
        self._node_concurrency = node_concurrency
        # For flow run, validate inputs as default
        with self._run_tracker.node_log_manager:
            # exec_line interface may be called by exec_bulk, so we only set run_mode as flow run when
            # it is not set.
            operation_context = OperationContext.get_instance()
            operation_context.run_mode = operation_context.get("run_mode", None) or RunMode.Test.name
            line_result = self._exec(
                inputs,
                run_id=run_id,
                line_number=index,
                variant_id=variant_id,
                validate_inputs=validate_inputs,
                allow_generator_output=allow_generator_output,
            )
        #  Return line result with index
        if index is not None and isinstance(line_result.output, dict):
            line_result.output[LINE_NUMBER_KEY] = index
        return line_result

    def _add_line_results(self, line_results: List[LineResult]):
        self._run_tracker._flow_runs.update({result.run_info.run_id: result.run_info for result in line_results})
        self._run_tracker._node_runs.update(
            {
                node_run_info.run_id: node_run_info
                for result in line_results
                for node_run_info in result.node_run_infos.values()
            }
        )

    def exec_bulk(
        self,
        inputs: List[Dict[str, Any]],
        run_id: str = None,
        validate_inputs: bool = True,
        raise_on_line_failure: bool = False,
        node_concurrency=DEFAULT_CONCURRENCY_BULK,
    ) -> BulkResult:
        """
        The entry points for bulk run execution

        Parameters
        ----------
        inputs:
            The batch inputs for the flow in the executor
        run_id:
            parent run id for current flow run, if any
            Todo: discuss with sdk if we keep this
        validate_inputs:
            flag to indicate if do inputs data validation
        raise_on_line_failure:
            flag to indicate if raise exception if line execution failed for bulk run

        Returns
        -------
            BulkResults including flow results and metrics
        """
        self._node_concurrency = node_concurrency
        run_id = run_id or str(uuid.uuid4())
        with self._run_tracker.node_log_manager:
            OperationContext.get_instance().run_mode = RunMode.Batch.name
            line_results = self._exec_batch_with_threads(inputs, run_id, validate_inputs=validate_inputs)
            self._add_line_results(line_results)  # For bulk run, currently we need to add line results to run_tracker
            self._handle_line_failures([r.run_info for r in line_results], raise_on_line_failure)
            aggr_results = self._exec_aggregation_with_bulk_results(inputs, line_results, run_id)
        outputs = [
            {LINE_NUMBER_KEY: r.run_info.index, **r.output}
            for r in line_results
            if r.run_info.status == Status.Completed
        ]
        return BulkResult(
            outputs=outputs,
            metrics=aggr_results.metrics,
            line_results=line_results,
            aggr_results=aggr_results,
        )

    def validate_and_apply_inputs_mapping(self, inputs, inputs_mapping):
        inputs_mapping = self._complete_inputs_mapping_by_default_value(inputs_mapping)
        resolved_inputs = self.apply_inputs_mapping_for_all_lines(inputs, inputs_mapping)
        return resolved_inputs

    def _complete_inputs_mapping_by_default_value(self, inputs_mapping):
        inputs_mapping = inputs_mapping or {}
        result_mapping = self.default_inputs_mapping
        result_mapping.update(inputs_mapping)
        return result_mapping

    def _exec(
        self,
        inputs: Mapping[str, Any],
        run_id: Optional[str] = None,
        line_number: Optional[int] = None,
        variant_id: str = "",
        validate_inputs: bool = False,
        allow_generator_output: bool = False,
    ) -> LineResult:
        """
        execute line run

        Args:
            inputs (Mapping): flow inputs
            run_id: the id to identify the flow run
            line_number: line number for batch inputs
            validate_inputs:
                Flag to indicate if input validation needed. It is used along with "_raise_ex" to
                define if exception shall be raised if inputs validation (type check, etc) failed
                The flag is True for Flow Run, False for bulk run as default
            allow_generator_output:
                Flag to indicate if generator output is allowed.


        Returns:
            LineResult: Line run result
        """
        run_id = run_id or str(uuid.uuid4())
        line_run_id = run_id if line_number is None else f"{run_id}_{line_number}"
        run_tracker = RunTracker(
            self._run_tracker._storage, self._run_tracker._run_mode, self._run_tracker.node_log_manager
        )
        # We need to copy the allow_generator_types from the original run_tracker.
        run_tracker.allow_generator_types = self._run_tracker.allow_generator_types
        run_info: FlowRunInfo = run_tracker.start_flow_run(
            flow_id=self._flow_id,
            root_run_id=run_id,
            run_id=line_run_id,
            parent_run_id=run_id,
            inputs={k: inputs[k] for k in self._flow.inputs if k in inputs},
            index=line_number,
            variant_id=variant_id,
        )
        context = FlowExecutionContext(
            name=self._flow.name,
            run_tracker=run_tracker,
            cache_manager=self._cache_manager,
            run_id=run_id,
            flow_id=self._flow_id,
            line_number=line_number,
            variant_id=variant_id,
        )
        output = {}
        aggregation_inputs = {}
        try:
            if validate_inputs:
                inputs = FlowValidator.ensure_flow_inputs_type(flow=self._flow, inputs=inputs, idx=line_number)
            output, nodes_outputs = self.traverse_nodes(inputs, context)
            output = self.stringify_generator_output(output) if not allow_generator_output else output
            run_tracker.allow_generator_types = allow_generator_output
            run_tracker.end_run(line_run_id, result=output)
            aggregation_inputs = self._extract_aggregation_inputs(nodes_outputs)
        except Exception as e:
            run_tracker.end_run(line_run_id, ex=e)
            if self._raise_ex:
                raise
        finally:
            run_tracker._update_flow_run_info_with_node_runs(run_info)
            run_tracker.persist_flow_run(run_info)
        node_run_infos = run_tracker.collect_child_node_runs(line_run_id)
        node_runs = {node_run.node: node_run for node_run in node_run_infos}
        return LineResult(output, aggregation_inputs, run_info, node_runs)

    def extract_outputs(self, nodes_outputs, flow_inputs):
        outputs = {}
        for name, output in self._flow.outputs.items():
            if output.reference.value_type == InputValueType.LITERAL:
                outputs[name] = output.reference.value
                continue
            if output.reference.value_type == InputValueType.FLOW_INPUT:
                outputs[name] = flow_inputs[output.reference.value]
                continue
            if output.reference.value_type != InputValueType.NODE_REFERENCE:
                raise NotImplementedError(f"Unsupported output type {output.reference.value_type}")
            node = next((n for n in self._flow.nodes if n.name == output.reference.value), None)
            if not node:
                raise ValueError(f"Invalid node name {output.reference.value}")
            if node.aggregation:
                # Note that the reduce node referenced in the output is not supported.
                continue
            if node.name not in nodes_outputs:
                raise ValueError(f"Node {output.reference.value} not found in results.")
            node_result = nodes_outputs[output.reference.value]
            outputs[name] = _input_assignment_parser.parse_node_property(
                output.reference.value, node_result, output.reference.property
            )
        return outputs

    def traverse_nodes(self, inputs, context: FlowExecutionContext) -> Tuple[dict, dict]:
        batch_nodes = [node for node in self._flow.nodes if not node.aggregation]
        outputs = {}
        nodes_outputs = self._submit_to_scheduler(context, inputs, batch_nodes)
        outputs = self.extract_outputs(nodes_outputs, inputs)
        return outputs, nodes_outputs

    def stringify_generator_output(self, outputs: dict):
        for k, v in outputs.items():
            if isinstance(v, GeneratorType):
                outputs[k] = "".join(str(chuck) for chuck in v)

        return outputs

    def _submit_to_scheduler(self, context: FlowExecutionContext, inputs, nodes: List[Node]) -> dict:
        if not isinstance(self._node_concurrency, int):
            raise NodeConcurrencyNotFound("Need to set node concurrency as using flow executor.")
        return FlowNodesScheduler(self._tools_manager).execute(context, inputs, nodes, self._node_concurrency)

    @staticmethod
    def apply_inputs_mapping_legacy(
        inputs: Mapping[str, Mapping[str, Any]],
        inputs_mapping: Mapping[str, str],
    ) -> Dict[str, Any]:
        """Apply inputs mapping to inputs for legacy contract.
        We use different inputs mapping foramt for new contract.

        For example:
        inputs: {
            "data": {"answer": 123, "question": "dummy"},
            "output": {"answer": 321},
            "baseline": {"answer": 322},
        }
        inputs_mapping: {
            "question": "data.question",  # Question from the data
            "groundtruth": "data.answer",  # Answer from the data
            "baseline": "baseline.answer",  # Answer from the baseline
            "answer": "output.answer",  # Answer from the output
            "deployment_name": "text-davinci-003",  # literal value
        }

        Returns: {
            "question": "dummy",
            "groundtruth": 123,
            "baseline": 322,
            "answer": 321,
            "deployment_name": "text-davinci-003",
        }
        """
        result = {}
        for k, v in inputs_mapping.items():
            if "." not in v:
                result[k] = v
                continue
            source, key = v.split(".", 1)
            if source in inputs:  # Value from inputs
                if key not in inputs[source]:
                    raise MappingSourceNotFound(
                        f"Failed to do input mapping for '{v}', can't find key '{key}' in dict '{source}', "
                        + f"all keys are {inputs[source].keys()}."
                    )
                result[k] = inputs[source][key]
            else:
                result[k] = v  # Literal value
        return result

    @staticmethod
    def apply_inputs_mapping(
        inputs: Mapping[str, Mapping[str, Any]],
        inputs_mapping: Mapping[str, str],
    ) -> Dict[str, Any]:
        """Apply inputs mapping to inputs for new contract.

        For example:
        inputs: {
            "data": {"answer": 123, "question": "dummy"},
            "baseline": {"answer": 322},
        }
        inputs_mapping: {
            "question": "${data.question}",  # Question from the data
            "groundtruth": "${data.answer}",  # Answer from the data
            "baseline": "${baseline.answer}",  # Answer from the baseline
            "deployment_name": "text-davinci-003",  # literal value
        }

        Returns: {
            "question": "dummy",
            "groundtruth": 123,
            "baseline": 322,
            "deployment_name": "text-davinci-003",
        }
        """
        import re

        result = {}
        notfound_mapping_relations = []
        for map_to_key, map_value in inputs_mapping.items():
            # Ignore reserved key configuration from inputs mapping.
            if map_to_key == LINE_NUMBER_KEY:
                continue
            if not isinstance(map_value, str):  # All non-string values are literal values.
                result[map_to_key] = map_value
                continue
            match = re.search(r"^\${([^{}]+)}$", map_value)
            if match is not None:
                pattern = match.group(1)
                # Could also try each paire of key value from inputs to match the pattern.
                # But split pattern by '.' is one deterministic way.
                # So, give key with less '.' higher priority.
                splitted_str = pattern.split(".")
                find_match = False
                for i in range(1, len(splitted_str)):
                    key = ".".join(splitted_str[:i])
                    source = ".".join(splitted_str[i:])
                    if key in inputs and source in inputs[key]:
                        find_match = True
                        result[map_to_key] = inputs[key][source]
                        break
                if not find_match:
                    notfound_mapping_relations.append(map_value)
            else:
                result[map_to_key] = map_value  # Literal value
        # Return all not found mapping relations in one exception to provide better debug experience.
        if notfound_mapping_relations:
            raise MappingSourceNotFound(
                f"Unable to find the following mapping relations: {', '.join(notfound_mapping_relations)}. "
                "Ensure that the keys and values in your input mapping align with those in your input data. "
                "If a mapping relation starts with '${data', it might have been generated from the YAML input file. "
                "In this case, you may need to assign it manually based on your input data."
            )
        # For PRS scenario, apply_inputs_mapping will be used for exec_line and line_number is not necessary.
        if LINE_NUMBER_KEY in inputs:
            result[LINE_NUMBER_KEY] = inputs[LINE_NUMBER_KEY]
        return result

    @staticmethod
    def _merge_input_dicts_by_line(
        input_dict: Mapping[str, List[Mapping[str, Any]]],
    ) -> List[Mapping[str, Mapping[str, Any]]]:
        for input_key, list_of_one_input in input_dict.items():
            if len(list_of_one_input) == 0:
                raise EmptyInputListError(f"List from key '{input_key}' is empty.")

        # Check if line numbers are aligned.
        all_lengths_without_line_number = {
            input_key: len(list_of_one_input)
            for input_key, list_of_one_input in input_dict.items()
            if not any(LINE_NUMBER_KEY in one_item for one_item in list_of_one_input)
        }
        if len(set(all_lengths_without_line_number.values())) > 1:
            raise LineNumberNotAlign(
                "Line numbers are not aligned. Some lists have dictionaries missing the 'line_number' key, "
                f"and the lengths of these lists are different. List lengths: {all_lengths_without_line_number}"
            )

        # Collect each line item from each input.
        tmp_dict = {}
        for input_key, list_of_one_input in input_dict.items():
            if input_key in all_lengths_without_line_number:
                # Assume line_number start from 0.
                for index, one_line_item in enumerate(list_of_one_input):
                    if index not in tmp_dict:
                        tmp_dict[index] = {}
                    tmp_dict[index][input_key] = one_line_item
            else:
                for one_line_item in list_of_one_input:
                    if LINE_NUMBER_KEY in one_line_item:
                        index = one_line_item[LINE_NUMBER_KEY]
                        if index not in tmp_dict:
                            tmp_dict[index] = {}
                        tmp_dict[index][input_key] = one_line_item
        result = []
        for line, valus_for_one_line in tmp_dict.items():
            # Missing input is not acceptable line.
            if len(valus_for_one_line) != len(input_dict):
                continue
            valus_for_one_line[LINE_NUMBER_KEY] = line
            result.append(valus_for_one_line)
        return result

    @staticmethod
    def apply_inputs_mapping_for_all_lines(
        input_dict: Mapping[str, List[Mapping[str, Any]]],
        inputs_mapping: Mapping[str, str],
    ) -> List[Dict[str, Any]]:
        """Apply inputs mapping to all input lines.

        For example:
        input_dict = {
            'data': [{'question': 'q1', 'answer': 'ans1'}, {'question': 'q2', 'answer': 'ans2'}],
            'baseline': [{'answer': 'baseline_ans1'}, {'answer': 'baseline_ans2'}],
            'output': [{'answer': 'output_ans1', 'line_number': 0}, {'answer': 'output_ans2', 'line_number': 1}],
        }
        inputs_mapping: {
            "question": "${data.question}",  # Question from the data
            "groundtruth": "${data.answer}",  # Answer from the data
            "baseline": "${baseline.answer}",  # Answer from the baseline
            "deployment_name": "text-davinci-003",  # literal value
            "answer": "${output.answer}",  # Answer from the output
            "line_number": "${output.line_number}",  # Answer from the output
        }

        Returns:
        [{
            "question": "q1",
            "groundtruth": "ans1",
            "baseline": "baseline_ans1",
            "answer": "output_ans1",
            "deployment_name": "text-davinci-003",
            "line_number": 0,
        },
        {
            "question": "q2",
            "groundtruth": "ans2",
            "baseline": "baseline_ans2",
            "answer": "output_ans2",
            "deployment_name": "text-davinci-003",
            "line_number": 1,
        }]
        """
        if inputs_mapping is None:
            # This exception should not happen since we should use default inputs_mapping if not provided.
            raise NoneInputsMappingIsNotSupported("Inputs mapping is None.")
        merged_list = FlowExecutor._merge_input_dicts_by_line(input_dict)
        if len(merged_list) == 0:
            raise EmptyInputAfterMapping("Input data does not contain a complete line. Please check your input.")

        result = [FlowExecutor.apply_inputs_mapping(item, inputs_mapping) for item in merged_list]
        return result

    def enable_streaming_for_llm_flow(self, stream_required: Callable[[], bool]):
        """Enable the LLM node that is connected to output to return streaming results controlled by stream_required.

        If the stream_required callback returns True, the LLM node will return a generator of strings.
        Otherwise, the LLM node will return a string.
        """
        for node in self._flow.nodes:
            if (
                self._flow.is_llm_node(node)
                and self._flow.is_referenced_by_flow_output(node)
                and not self._flow.is_referenced_by_other_node(node)
            ):
                self._tools_manager.wrap_tool(node.name, wrapper=inject_stream_options(stream_required))

    def ensure_flow_is_serializable(self):
        """Ensure that the flow is serializable.

        Some of the nodes may return a generator of strings to create streaming outputs.
        This is useful when the flow is deployed as a web service.
        However, in the interactive mode, the executor assumes that the node result is JSON serializable.

        This method adds a wrapper to each node in the flow
        to consume the streaming outputs and merge them into a string for executor usage.
        """
        for node in self._flow.nodes:
            self._tools_manager.wrap_tool(node.name, wrapper=ensure_node_result_is_serializable)


def inject_stream_options(should_stream: Callable[[], bool]):
    """Inject the stream options to the decorated function.

    AzureOpenAI.completion and AzureOpenAI.chat tools support both stream and non-stream mode.
    The stream mode is controlled by the "stream" parameter.
    """

    def stream_option_decorator(f):
        # We only wrap the function if it has a "stream" parameter
        signature = inspect.signature(f)
        if "stream" not in signature.parameters:
            return f

        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            kwargs = kwargs or {}
            kwargs.update(stream=should_stream())

            return f(*args, **kwargs)

        return wrapper

    return stream_option_decorator


def enable_streaming_for_llm_tool(f):
    """Enable the stream mode for LLM tools that supports it.

    AzureOpenAI.completion and AzureOpenAI.chat tools support both stream and non-stream mode.
    The stream mode is turned off by default. Use this wrapper to turn it on.
    """

    # We only wrap the function if it has a "stream" parameter
    signature = inspect.signature(f)
    if "stream" not in signature.parameters:
        return f

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        kwargs = kwargs or {}
        kwargs.update(stream=True)

        return f(*args, **kwargs)

    return wrapper


def ensure_node_result_is_serializable(f):
    """Ensure the node result is serializable.

    Some of the nodes may return a generator of strings to create streaming outputs.
    This is useful when the flow is deployed as a web service.
    However, in the interactive mode, the executor assumes that the node result is JSON serializable.

    This wrapper ensures the node result is serializable
    by consuming the data from the generator and merging them into a string.
    """

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        result = f(*args, **kwargs)
        if isinstance(result, GeneratorType):
            result = "".join(str(trunk) for trunk in result)
        return result

    return wrapper


class InputMappingError(ValidationException):
    def __init__(self, message, target=ErrorTarget.FLOW_EXECUTOR):
        super().__init__(message=message, target=target)


class LineNumberNotAlign(InputMappingError):
    pass


class MappingSourceNotFound(InputMappingError):
    pass


class EmptyInputListError(InputMappingError):
    pass


class EmptyInputAfterMapping(InputMappingError):
    pass


class NoneInputsMappingIsNotSupported(SystemErrorException):
    pass


class NodeResultCountNotMatch(SystemErrorException):
    pass
