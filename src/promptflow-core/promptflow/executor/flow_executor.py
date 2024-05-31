# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import asyncio
import contextlib
import copy
import functools
import inspect
import os
import signal
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path
from threading import current_thread
from typing import Any, AsyncIterator, Callable, Dict, Iterator, List, Mapping, Optional, Tuple, Union

import opentelemetry.trace as otel_trace
from opentelemetry.trace.span import Span, format_trace_id
from opentelemetry.trace.status import StatusCode

from promptflow._constants import LINE_NUMBER_KEY, FlowType
from promptflow._core._errors import NotSupported, UnexpectedError
from promptflow._core.cache_manager import AbstractCacheManager
from promptflow._core.flow_execution_context import FlowExecutionContext
from promptflow._core.metric_logger import add_metric_logger, remove_metric_logger
from promptflow._core.run_tracker import RunTracker
from promptflow._core.tool import STREAMING_OPTION_PARAMETER_ATTR
from promptflow._core.tools_manager import ToolsManager
from promptflow._utils.async_utils import async_run_allowing_running_loop, sync_iterator_to_async
from promptflow._utils.context_utils import _change_working_dir
from promptflow._utils.execution_utils import (
    apply_default_value_for_input,
    extract_aggregation_inputs,
    get_aggregation_inputs_properties,
)
from promptflow._utils.flow_utils import is_flex_flow, is_prompty_flow
from promptflow._utils.logger_utils import flow_logger, logger
from promptflow._utils.multimedia_utils import MultimediaProcessor
from promptflow._utils.user_agent_utils import append_promptflow_package_ua
from promptflow._utils.utils import get_int_env_var
from promptflow._utils.yaml_utils import load_yaml
from promptflow.connections import ConnectionProvider
from promptflow.contracts.flow import Flow, FlowInputDefinition, InputAssignment, InputValueType, Node
from promptflow.contracts.run_info import FlowRunInfo
from promptflow.contracts.run_mode import RunMode
from promptflow.core import Prompty
from promptflow.core._connection_provider._dict_connection_provider import DictConnectionProvider
from promptflow.exceptions import PromptflowException
from promptflow.executor import _input_assignment_parser
from promptflow.executor._async_nodes_scheduler import AsyncNodesScheduler
from promptflow.executor._errors import NodeOutputNotFound, OutputReferenceNotExist, SingleNodeValidationError
from promptflow.executor._flow_nodes_scheduler import (
    DEFAULT_CONCURRENCY_BULK,
    DEFAULT_CONCURRENCY_FLOW,
    FlowNodesScheduler,
)
from promptflow.executor._result import AggregationResult, LineResult
from promptflow.executor._tool_resolver import ToolResolver
from promptflow.executor.flow_validator import FlowValidator
from promptflow.storage import AbstractRunStorage
from promptflow.storage._run_storage import DefaultRunStorage
from promptflow.tracing import ThreadPoolExecutorWithContext
from promptflow.tracing._integrations._openai_injector import inject_openai_api
from promptflow.tracing._operation_context import OperationContext
from promptflow.tracing._start_trace import setup_exporter_from_environ
from promptflow.tracing._trace import (
    enrich_span_with_context,
    enrich_span_with_input,
    enrich_span_with_trace_type,
    start_as_current_span,
)
from promptflow.tracing.contracts.trace import TraceType

DEFAULT_TRACING_KEYS = {"run_mode", "root_run_id", "flow_id", "batch_input_source", "execution_target"}


class FlowExecutor:
    """This class is used to execute a single flow for different inputs.

    :param flow: The flow to be executed.
    :type flow: ~promptflow.contracts.flow.Flow
    :param connections: The connections to be used for the flow.
    :type connections: dict
    :param run_tracker: The run tracker to be used for the flow.
    :type run_tracker: ~promptflow._core.run_tracker.RunTracker
    :param cache_manager: The cache manager to be used for the flow.
    :type cache_manager: ~promptflow._core.cache_manager.AbstractCacheManager
    :param loaded_tools: The loaded tools to be used for the flow.
    :type loaded_tools: Mapping[str, Callable]
    :param worker_count: The number of workers to be used for the flow. Default is 16.
    :type worker_count: Optional[int]
    :param raise_ex: Whether to raise exceptions or not. Default is False.
    :type raise_ex: Optional[bool]
    :param working_dir: The working directory to be used for the flow. Default is None.
    :type working_dir: Optional[str]
    :param line_timeout_sec: The line timeout in seconds to be used for the flow. Default is LINE_TIMEOUT_SEC.
    :type line_timeout_sec: Optional[int]
    :param flow_file: The flow file to be used for the flow. Default is None.
    :type flow_file: Optional[Path]
    """

    def __init__(
        self,
        flow: Flow,
        connections: ConnectionProvider,
        run_tracker: RunTracker,
        cache_manager: AbstractCacheManager,
        loaded_tools: Mapping[str, Callable],
        *,
        raise_ex: bool = False,
        working_dir=None,
        line_timeout_sec=None,
        flow_file=None,
    ):
        """Initialize a FlowExecutor object.

        :param flow: The Flow object to execute.
        :type flow: ~promptflow.contracts.flow.Flow
        :param connections: The connections between nodes in the Flow.
        :type connections: Union[dict, ConnectionProvider]
        :param run_tracker: The RunTracker object to track the execution of the Flow.
        :type run_tracker: ~promptflow._core.run_tracker.RunTracker
        :param cache_manager: The AbstractCacheManager object to manage caching of results.
        :type cache_manager: ~promptflow._core.cache_manager.AbstractCacheManager
        :param loaded_tools: A mapping of tool names to their corresponding functions.
        :type loaded_tools: Mapping[str, Callable]
        :param raise_ex: Whether to raise an exception if an error occurs during execution.
        :type raise_ex: bool
        :param working_dir: The working directory to use for execution.
        :type working_dir: str or None
        :param line_timeout_sec: The maximum time to wait for a line of output from a node.
        :type line_timeout_sec: int or None
        :param flow_file: The path to the file containing the Flow definition.
        :type flow_file: str or None
        """
        self._flow = flow
        self._flow_id = flow.id or str(uuid.uuid4())
        self._connections = connections
        self._aggregation_inputs_references = get_aggregation_inputs_properties(flow)
        self._aggregation_nodes = {node.name for node in self._flow.nodes if node.aggregation}
        self._run_tracker = run_tracker
        self._cache_manager = cache_manager
        self._loaded_tools = loaded_tools
        self._working_dir = working_dir
        self._line_timeout_sec = line_timeout_sec or get_int_env_var("PF_LINE_TIMEOUT_SEC")
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
        self._message_format = flow.message_format
        self._multimedia_processor = MultimediaProcessor.create(flow.message_format)

    # This field is used to distinguish the execution target of the flow.
    # Candidate value for executors are dag, flex adn prompty.
    _execution_target = FlowType.DAG_FLOW

    @classmethod
    def create(
        cls,
        flow_file: Path,
        connections: Union[dict, ConnectionProvider],
        working_dir: Optional[Path] = None,
        *,
        entry: Optional[str] = None,
        storage: Optional[AbstractRunStorage] = None,
        raise_ex: bool = True,
        node_override: Optional[Dict[str, Dict[str, Any]]] = None,
        line_timeout_sec: Optional[int] = None,
        init_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> "FlowExecutor":
        """Create a new instance of FlowExecutor.

        :param flow_file: The path to the flow file.
        :type flow_file: Path
        :param connections: The connections to be used for the flow.
        :type connections: Union[dict, ConnectionProvider]
        :param working_dir: The working directory to be used for the flow. Default is None.
        :type working_dir: Optional[str]
        :param func: The function to be used for the flow if .py is provided. Default is None.
        :type func: Optional[str]
        :param storage: The storage to be used for the flow. Default is None.
        :type storage: Optional[~promptflow.storage.AbstractRunStorage]
        :param raise_ex: Whether to raise exceptions or not. Default is True.
        :type raise_ex: Optional[bool]
        :param node_override: The node overrides to be used for the flow. Default is None.
        :type node_override: Optional[Dict[str, Dict[str, Any]]]
        :param line_timeout_sec: The line timeout in seconds to be used for the flow. Default is LINE_TIMEOUT_SEC.
        :type line_timeout_sec: Optional[int]
        :param init_kwargs: Class init arguments for callable class, only supported for flex flow.
        :type init_kwargs: Optional[Dict[str, Any]]
        :return: A new instance of FlowExecutor.
        :rtype: ~promptflow.executor.flow_executor.FlowExecutor
        """
        env_exporter_setup = kwargs.get("env_exporter_setup", True)
        if env_exporter_setup:
            setup_exporter_from_environ()

        if isinstance(flow_file, Prompty):
            from ._prompty_executor import PromptyExecutor

            return PromptyExecutor(flow_file=flow_file, working_dir=working_dir, storage=storage)
        if hasattr(flow_file, "__call__") or inspect.isfunction(flow_file):
            from ._script_executor import ScriptExecutor

            return ScriptExecutor(flow_file, connections=connections, storage=storage)
        if not isinstance(flow_file, (Path, str)):
            raise NotImplementedError("Only support Path or str for flow_file.")
        if is_flex_flow(flow_path=flow_file, working_dir=working_dir):
            from ._script_executor import ScriptExecutor

            return ScriptExecutor(
                flow_file=Path(flow_file),
                connections=connections,
                working_dir=working_dir,
                storage=storage,
                init_kwargs=init_kwargs,
            )
        elif is_prompty_flow(file_path=flow_file):
            from ._prompty_executor import PromptyExecutor

            return PromptyExecutor(
                flow_file=Path(flow_file),
                working_dir=working_dir,
                storage=storage,
                init_kwargs=init_kwargs,
            )
        else:
            if init_kwargs:
                logger.warning(f"Got unexpected init args {init_kwargs} for non-script flow. Ignoring them.")

            name = kwargs.get("name", None)
            flow = Flow.from_yaml(flow_file, working_dir=working_dir, name=name)
            return cls._create_from_flow(
                flow_file=flow_file,
                flow=flow,
                connections=connections,
                working_dir=working_dir,
                storage=storage,
                raise_ex=raise_ex,
                node_override=node_override,
                line_timeout_sec=line_timeout_sec,
            )

    @classmethod
    def _create_from_flow(
        cls,
        flow: Flow,
        connections: Union[dict, ConnectionProvider],
        working_dir: Optional[Path],
        *,
        flow_file: Optional[Path] = None,
        storage: Optional[AbstractRunStorage] = None,
        raise_ex: bool = True,
        node_override: Optional[Dict[str, Dict[str, Any]]] = None,
        line_timeout_sec: Optional[int] = None,
    ):
        logger.debug("Start initializing the flow executor.")
        working_dir = Flow._resolve_working_dir(flow_file, working_dir)
        if node_override:
            flow = flow._apply_node_overrides(node_override)
        flow = flow._apply_default_node_variants()

        package_tool_keys = [node.source.tool for node in flow.nodes if node.source and node.source.tool]
        if isinstance(connections, dict):
            connections = DictConnectionProvider(connections)
        tool_resolver = ToolResolver(working_dir, connections, package_tool_keys, message_format=flow.message_format)

        with _change_working_dir(working_dir):
            resolved_tools = [tool_resolver.resolve_tool_by_node(node) for node in flow.nodes]
        flow = Flow(
            id=flow.id,
            name=flow.name,
            nodes=[r.node for r in resolved_tools],
            inputs=flow.inputs,
            outputs=flow.outputs,
            tools=[],
            message_format=flow.message_format,
        )
        # ensure_flow_valid including validation + resolve
        # Todo: 1) split pure validation + resolve from below method 2) provide completed validation()
        flow = FlowValidator._validate_nodes_topology(flow)
        flow.outputs = FlowValidator._ensure_outputs_valid(flow)

        run_tracker = RunTracker(storage)

        cache_manager = AbstractCacheManager.init_from_env()

        executor = FlowExecutor(
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
        logger.debug("The flow executor is initialized successfully.")
        return executor

    @classmethod
    def load_and_exec_node(
        cls,
        flow_file: Path,
        node_name: str,
        *,
        storage: AbstractRunStorage = None,
        output_sub_dir: Optional[str] = None,
        flow_inputs: Optional[Mapping[str, Any]] = None,
        dependency_nodes_outputs: Optional[Mapping[str, Any]] = None,
        connections: Optional[dict] = None,
        working_dir: Optional[Path] = None,
        raise_ex: bool = False,
    ):
        """Load and execute a single node from the flow.

        :param flow_file: The path to the flow file.
        :type flow_file: Path
        :param node_name: The name of the node to be executed.
        :type node_name: str
        :param storage: The storage to be used for the flow.
        :type storage: Optional[~promptflow.storage.AbstractRunStorage]
        :param output_sub_dir: The directory to persist image for the flow. Keep it only for backward compatibility.
        :type output_sub_dir: Optional[str]
        :param flow_inputs: The inputs to be used for the flow. Default is None.
        :type flow_inputs: Optional[Mapping[str, Any]]
        :param dependency_nodes_outputs: The outputs of the dependency nodes. Default is None.
        :type dependency_nodes_outputs: Optional[Mapping[str, Any]
        :param connections: The connections to be used for the flow. Default is None.
        :type connections: Optional[dict]
        :param working_dir: The working directory to be used for the flow. Default is None.
        :type working_dir: Optional[str]
        :param raise_ex: Whether to raise exceptions or not. Default is False.
        :type raise_ex: Optional[bool]
        """

        @contextlib.contextmanager
        def update_operation_context():
            operation_context = OperationContext.get_instance()
            original_context = operation_context.copy()
            try:
                append_promptflow_package_ua(operation_context)
                operation_context.set_execution_target(cls._execution_target)
                operation_context.set_default_tracing_keys(DEFAULT_TRACING_KEYS)
                operation_context["run_mode"] = RunMode.SingleNode.name
                # Inject OpenAI API to make sure traces and headers injection works and
                # update OpenAI API configs from environment variables.
                inject_openai_api()
                yield
            finally:
                OperationContext.set_instance(original_context)

        # Register signal handler for SIGINT and SIGTERM to cancel the single node run.
        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

        dependency_nodes_outputs = dependency_nodes_outputs or {}
        # Load the node from the flow file
        working_dir = Flow._resolve_working_dir(flow_file, working_dir)
        with open(working_dir / flow_file, "r") as fin:
            flow = Flow.deserialize(load_yaml(fin))
        node = flow.get_node(node_name)
        if node is None:
            raise SingleNodeValidationError(
                message_format=(
                    "Validation failed when attempting to execute the node. "
                    "Node '{node_name}' is not found in flow '{flow_file}'. "
                    "Please change node name or correct the flow file."
                ),
                node_name=node_name,
                flow_file=flow_file,
            )
        if not node.source or not node.type:
            raise SingleNodeValidationError(
                message_format=(
                    "Validation failed when attempting to execute the node. "
                    "Properties 'source' or 'type' are not specified for Node '{node_name}' in flow '{flow_file}'. "
                    "Please make sure these properties are in place and try again."
                ),
                node_name=node_name,
                flow_file=flow_file,
            )
        # Only load the node's referenced flow inputs
        node_referenced_flow_inputs = FlowExecutor._get_node_referenced_flow_inputs(node, flow.inputs)
        inputs_with_default_value = apply_default_value_for_input(node_referenced_flow_inputs, flow_inputs)
        converted_flow_inputs_for_node = FlowValidator.convert_flow_inputs_for_node(
            flow, node, inputs_with_default_value
        )

        multimedia_processor = MultimediaProcessor.create(flow.message_format)
        inputs = multimedia_processor.load_multimedia_data(node_referenced_flow_inputs, converted_flow_inputs_for_node)
        dependency_nodes_outputs = multimedia_processor.load_multimedia_data_recursively(dependency_nodes_outputs)
        package_tool_keys = [node.source.tool] if node.source and node.source.tool else []
        if isinstance(connections, dict):
            connections = DictConnectionProvider(connections)
        tool_resolver = ToolResolver(working_dir, connections, package_tool_keys, message_format=flow.message_format)
        resolved_node = tool_resolver.resolve_tool_by_node(node)

        # Prepare callable and real inputs here

        resolved_inputs = {}
        for k, v in resolved_node.node.inputs.items():
            value = _input_assignment_parser.parse_value(v, dependency_nodes_outputs, inputs)
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

        if storage is None:
            sub_dir = "." if output_sub_dir is None else output_sub_dir
            storage = DefaultRunStorage(base_dir=working_dir, sub_dir=Path(sub_dir))

        run_tracker = RunTracker(storage)
        with run_tracker.node_log_manager, update_operation_context():
            # Will generate node run in context
            context = FlowExecutionContext(
                name=flow.name,
                run_tracker=run_tracker,
                cache_manager=AbstractCacheManager.init_from_env(),
                message_format=flow.message_format,
            )

            try:
                if inspect.iscoroutinefunction(resolved_node.callable):
                    asyncio.run(
                        context.invoke_tool_async(resolved_node.node, resolved_node.callable, kwargs=resolved_inputs),
                    )
                else:
                    context.invoke_tool(resolved_node.node, resolved_node.callable, kwargs=resolved_inputs)
            except KeyboardInterrupt:
                run_tracker.cancel_node_runs()
            except Exception:
                if raise_ex:  # Only raise exception when raise_ex is True
                    raise

            node_runs = run_tracker.collect_node_runs()
            if len(node_runs) != 1:
                # Should not happen except there is bug in run_tracker or thread control.
                raise UnexpectedError(
                    message_format=(
                        "Single node execution failed. Expected one node result, "
                        "but received {node_result_num}. Please contact support for further assistance."
                    ),
                    node_result_num=len(node_runs),
                )
            return node_runs[0]

    @staticmethod
    def update_environment_variables_with_connections(connections: dict):
        """Update environment variables with connections.

        :param connections: A dictionary containing connection information.
        :type connections: dict
        :return: A dictionary containing updated environment variables.
        :rtype: dict
        """
        from promptflow.core._utils import update_environment_variables_with_connections

        return update_environment_variables_with_connections(connections)

    def convert_flow_input_types(self, inputs: dict) -> Mapping[str, Any]:
        """Convert the input types of the given inputs dictionary to match the expected types of the flow.

        :param inputs: A dictionary containing the inputs to the flow.
        :type inputs: dict
        :return: A dictionary containing the converted inputs.
        :rtype: Mapping[str, Any]
        """
        return FlowValidator.resolve_flow_inputs_type(self._flow, inputs)

    @property
    def _default_inputs_mapping(self):
        return {key: f"${{data.{key}}}" for key in self._flow.inputs}

    @property
    def has_aggregation_node(self) -> bool:
        """Check if the flow executor has any aggregation nodes.

        :return: True if the flow executor has at least one aggregation node, False otherwise.
        :rtype: bool
        """
        return len(self._aggregation_nodes) > 0

    @property
    def aggregation_nodes(self):
        """Get the aggregation nodes of the flow executor.

        :return: A list of aggregation nodes.
        :rtype: list
        """
        return self._aggregation_nodes

    def _fill_lines(self, indexes, values, nlines):
        """Fill the values into the result list according to the indexes."""
        result = [None] * nlines
        for idx, value in zip(indexes, values):
            result[idx] = value
        return result

    @staticmethod
    def _try_get_aggregation_input(val: InputAssignment, aggregation_inputs: dict):
        if val.value_type != InputValueType.NODE_REFERENCE:
            return val
        serialized_val = val.serialize()
        if serialized_val not in aggregation_inputs:
            return val
        return InputAssignment(value=aggregation_inputs[serialized_val])

    def get_status_summary(self, run_id: str):
        """Get a summary of the status of a given run.

        :param run_id: The ID of the run to get the status summary for.
        :type run_id: str
        :return: A summary of the status of the given run.
        :rtype: str
        """
        return self._run_tracker.get_status_summary(run_id)

    def exec_aggregation(
        self,
        inputs: Mapping[str, Any],
        aggregation_inputs: Mapping[str, Any],
        run_id=None,
        node_concurrency=DEFAULT_CONCURRENCY_FLOW,
    ) -> AggregationResult:
        """Execute the aggregation node of the flow.

        :param inputs: A mapping of input names to their values.
        :type inputs: Mapping[str, Any]
        :param aggregation_inputs: A mapping of aggregation input names to their values.
        :type aggregation_inputs: Mapping[str, Any]
        :param run_id: The ID of the current run, if any.
        :type run_id: Optional[str]
        :param node_concurrency: The maximum number of nodes that can be executed concurrently.
        :type node_concurrency: int
        :return: The result of the aggregation node.
        :rtype: ~promptflow.executor._result.AggregationResult
        :raises: FlowError if the inputs or aggregation_inputs are invalid.
        """
        self._node_concurrency = node_concurrency
        aggregated_flow_inputs = dict(inputs or {})
        aggregation_inputs = dict(aggregation_inputs or {})
        FlowValidator._validate_aggregation_inputs(aggregated_flow_inputs, aggregation_inputs)
        aggregated_flow_inputs = self._apply_default_value_for_aggregation_input(
            self._flow.inputs, aggregated_flow_inputs, aggregation_inputs
        )

        # Resolve aggregated_flow_inputs from list of strings to list of objects, whose type is specified in yaml file.
        resolved_aggregated_flow_inputs = FlowValidator.resolve_aggregated_flow_inputs_type(
            self._flow, aggregated_flow_inputs
        )
        with self._run_tracker.node_log_manager, self._update_operation_context_for_aggregation(run_id=run_id):
            return self._exec_aggregation(resolved_aggregated_flow_inputs, aggregation_inputs, run_id)

    @staticmethod
    def _apply_default_value_for_aggregation_input(
        inputs: Dict[str, FlowInputDefinition],
        aggregated_flow_inputs: Mapping[str, Any],
        aggregation_inputs: Mapping[str, Any],
    ):
        aggregation_lines = 1
        if aggregated_flow_inputs.values():
            one_input_value = list(aggregated_flow_inputs.values())[0]
            aggregation_lines = len(one_input_value)
        # If aggregated_flow_inputs is empty, we should use aggregation_inputs to get the length.
        elif aggregation_inputs.values():
            one_input_value = list(aggregation_inputs.values())[0]
            aggregation_lines = len(one_input_value)
        for key, value in inputs.items():
            if key not in aggregated_flow_inputs and (value and value.default is not None):
                aggregated_flow_inputs[key] = [value.default] * aggregation_lines
        return aggregated_flow_inputs

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
        # Load multimedia data from aggregation_inputs
        aggregation_inputs = self._multimedia_processor.load_multimedia_data_recursively(aggregation_inputs)
        # Update the inputs of the aggregation nodes with the aggregation inputs.
        for node in nodes:
            node.inputs = {
                k: FlowExecutor._try_get_aggregation_input(v, aggregation_inputs) for k, v in node.inputs.items()
            }
        # Load multimedia data for the flow inputs of aggregation nodes.
        inputs = self._multimedia_processor.load_multimedia_data(self._flow.inputs, inputs)

        # TODO: Use a new run tracker to avoid memory increase infinitely.
        run_tracker = self._run_tracker
        context = FlowExecutionContext(
            name=self._flow.name,
            run_tracker=run_tracker,
            cache_manager=self._cache_manager,
            run_id=run_id,
            flow_id=self._flow_id,
            message_format=self._message_format,
        )
        metrics = {}

        def _log_metric(key, value):
            metrics[key] = value

        add_metric_logger(_log_metric)
        try:
            self._submit_to_scheduler(context, inputs, nodes)
        except KeyboardInterrupt:
            # Cancel all the running node runs if receiving KeyboardInterrupt.
            run_tracker.cancel_node_runs(run_id)
        except Exception:
            if self._raise_ex:
                raise
        finally:
            remove_metric_logger(_log_metric)
        node_run_infos = run_tracker.collect_child_node_runs(run_id)
        # Output is set as an empty dict, because the aggregation outputs story is not finalized.
        return AggregationResult({}, metrics, {run.node: run for run in node_run_infos})

    def exec(self, inputs: dict, node_concurrency=DEFAULT_CONCURRENCY_FLOW) -> dict:
        """Executes the flow with the given inputs and returns the output.

        :param inputs: A dictionary containing the input values for the flow.
        :type inputs: dict
        :param node_concurrency: The maximum number of nodes that can be executed concurrently.
        :type node_concurrency: int
        :return: A dictionary containing the output values of the flow.
        :rtype: dict
        """
        self._node_concurrency = node_concurrency
        inputs = apply_default_value_for_input(self._flow.inputs, inputs)
        result = self._exec(inputs)
        #  TODO: remove this line once serving directly calling self.exec_line
        self._add_line_results([result])
        return result.output or {}

    def _exec_in_thread(self, args) -> LineResult:
        inputs, run_id, line_number, validate_inputs = args
        thread_name = current_thread().name
        self._processing_idx[line_number] = thread_name
        self._run_tracker._activate_in_context()
        results = self._exec(inputs, run_id=run_id, line_number=line_number, validate_inputs=validate_inputs)
        self._run_tracker._deactivate_in_context()
        self._processing_idx.pop(line_number)
        self._completed_idx[line_number] = thread_name
        return results

    def get_inputs_definition(self):
        return self._flow.inputs

    def exec_line(
        self,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
        validate_inputs: bool = True,
        node_concurrency=DEFAULT_CONCURRENCY_FLOW,
        allow_generator_output: bool = False,
        line_timeout_sec: Optional[int] = None,
    ) -> LineResult:
        """Execute a single line of the flow.

        :param inputs: The input values for the line.
        :type inputs: Mapping[str, Any]
        :param index: The index of the line to execute.
        :type index: Optional[int]
        :param run_id: The ID of the flow run.
        :type run_id: Optional[str]
        :param validate_inputs: Whether to validate the input values.
        :type validate_inputs: bool
        :param node_concurrency: The maximum number of nodes that can be executed concurrently.
        :type node_concurrency: int
        :param allow_generator_output: Whether to allow generator output.
        :type allow_generator_output: bool
        :param line_timeout_sec: The maximum time to wait for a line of output.
        :type line_timeout_sec: Optional[int]
        :return: The result of executing the line.
        :rtype: ~promptflow.executor._result.LineResult
        """
        if self._should_use_async():
            #  Use async exec_line when the tools are async
            return async_run_allowing_running_loop(
                self.exec_line_async,
                inputs,
                index,
                run_id,
                validate_inputs,
                node_concurrency,
                allow_generator_output,
                line_timeout_sec,
                sync_iterator_to_async=False,
            )
        # TODO: Call exec_line_async in exec_line when async is mature.
        self._node_concurrency = node_concurrency
        # TODO: Pass line_timeout_sec to flow node scheduler instead of updating self._line_timeout_sec
        self._line_timeout_sec = line_timeout_sec or self._line_timeout_sec
        inputs = apply_default_value_for_input(self._flow.inputs, inputs)
        # For flow run, validate inputs as default
        run_id = run_id or str(uuid.uuid4())
        with self._run_tracker.node_log_manager, self._update_operation_context(run_id, index):
            line_result = self._exec(
                inputs,
                run_id=run_id,
                line_number=index,
                validate_inputs=validate_inputs,
                allow_generator_output=allow_generator_output,
            )
        #  Return line result with index
        if index is not None and isinstance(line_result.output, dict):
            line_result.output[LINE_NUMBER_KEY] = index
        return line_result

    async def exec_line_async(
        self,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
        validate_inputs: bool = True,
        node_concurrency=DEFAULT_CONCURRENCY_FLOW,
        allow_generator_output: bool = False,
        line_timeout_sec: Optional[int] = None,
        sync_iterator_to_async: bool = True,
    ) -> LineResult:
        """Execute a single line of the flow.

        :param inputs: The input values for the line.
        :type inputs: Mapping[str, Any]
        :param index: The index of the line to execute.
        :type index: Optional[int]
        :param run_id: The ID of the flow run.
        :type run_id: Optional[str]
        :param validate_inputs: Whether to validate the input values.
        :type validate_inputs: bool
        :param node_concurrency: The maximum number of nodes that can be executed concurrently.
        :type node_concurrency: int
        :param allow_generator_output: Whether to allow generator output.
        :type allow_generator_output: bool
        :param sync_iterator_to_async: Whether to convert sync iterator output to async iterator.
        :type sync_iterator_to_async: bool
        :return: The result of executing the line.
        :rtype: ~promptflow.executor._result.LineResult
        """
        self._node_concurrency = node_concurrency
        # TODO: Pass line_timeout_sec to flow node scheduler instead of updating self._line_timeout_sec
        self._line_timeout_sec = line_timeout_sec or self._line_timeout_sec
        inputs = apply_default_value_for_input(self._flow.inputs, inputs)
        # For flow run, validate inputs as default
        run_id = run_id or str(uuid.uuid4())
        with self._run_tracker.node_log_manager, self._update_operation_context(run_id, index):
            line_result = await self._exec_async(
                inputs,
                run_id=run_id,
                line_number=index,
                validate_inputs=validate_inputs,
                allow_generator_output=allow_generator_output,
            )
            if sync_iterator_to_async:
                line_result.output = self._convert_iterators_to_async(line_result.output)
        #  Return line result with index
        if index is not None and isinstance(line_result.output, dict):
            line_result.output[LINE_NUMBER_KEY] = index
        return line_result

    @contextlib.contextmanager
    def _update_operation_context(self, run_id: str, line_number: int):
        operation_context = OperationContext.get_instance()
        original_context = operation_context.copy()
        original_mode = operation_context.get("run_mode", RunMode.Test.name)
        values_for_context = {"flow_id": self._flow_id, "root_run_id": run_id}
        if original_mode == RunMode.Batch.name:
            values_for_otel = {
                "batch_run_id": run_id,
                "line_number": line_number,
            }
        else:
            values_for_otel = {"line_run_id": run_id}
        try:
            append_promptflow_package_ua(operation_context)
            operation_context.set_execution_target(execution_target=self._execution_target)
            operation_context.set_default_tracing_keys(DEFAULT_TRACING_KEYS)
            operation_context.run_mode = original_mode
            operation_context.update(values_for_context)
            for k, v in values_for_otel.items():
                operation_context._add_otel_attributes(k, v)
            # Inject OpenAI API to make sure traces and headers injection works and
            # update OpenAI API configs from environment variables.
            inject_openai_api()
            yield
        finally:
            OperationContext.set_instance(original_context)

    @contextlib.contextmanager
    def _update_operation_context_for_aggregation(self, run_id: str):
        operation_context = OperationContext.get_instance()
        original_context = operation_context.copy()
        original_mode = operation_context.get("run_mode", RunMode.Test.name)
        values_for_context = {"flow_id": self._flow_id, "root_run_id": run_id}
        values_for_otel = {"is_aggregation": True}
        # Add batch_run_id here because one aggregate node exists under the batch run concept.
        # Don't add line_run_id because it doesn't exist under the line run concept.
        if original_mode == RunMode.Batch.name:
            values_for_otel.update(
                {
                    "batch_run_id": run_id,
                }
            )
        try:
            append_promptflow_package_ua(operation_context)
            operation_context.set_execution_target(self._execution_target)
            operation_context.set_default_tracing_keys(DEFAULT_TRACING_KEYS)
            operation_context.run_mode = original_mode
            operation_context.update(values_for_context)
            for k, v in values_for_otel.items():
                operation_context._add_otel_attributes(k, v)
            # Inject OpenAI API to make sure traces and headers injection works and
            # update OpenAI API configs from environment variables.
            inject_openai_api()
            yield
        finally:
            OperationContext.set_instance(original_context)

    def _add_line_results(self, line_results: List[LineResult], run_tracker: Optional[RunTracker] = None):
        run_tracker = run_tracker or self._run_tracker
        run_tracker._flow_runs.update({result.run_info.run_id: result.run_info for result in line_results})
        run_tracker._node_runs.update(
            {
                node_run_info.run_id: node_run_info
                for result in line_results
                for node_run_info in result.node_run_infos.values()
            }
        )

    @staticmethod
    def _get_node_referenced_flow_inputs(
        node, flow_inputs: Dict[str, FlowInputDefinition]
    ) -> Dict[str, FlowInputDefinition]:
        node_referenced_flow_inputs = {}
        for _, value in node.inputs.items():
            # Only add flow input to node_referenced_flow_inputs when it is exist and referenced by node.
            # If flow input is not exist, we will raise exception in FlowValidator.convert_flow_inputs_for_node.
            if value.value_type == InputValueType.FLOW_INPUT and value.value in flow_inputs:
                node_referenced_flow_inputs[value.value] = flow_inputs[value.value]
        return node_referenced_flow_inputs

    @staticmethod
    def _tracing_disabled():
        return os.environ.get("PF_DISABLE_TRACING", "false").lower() == "true"

    @contextlib.contextmanager
    def _start_flow_span(self, inputs: Mapping[str, Any]):
        if FlowExecutor._tracing_disabled():
            yield None
            return
        otel_tracer = otel_trace.get_tracer("promptflow")
        with start_as_current_span(otel_tracer, self._flow.name) as span:
            # Store otel trace id in context for correlation
            OperationContext.get_instance()["otel_trace_id"] = f"0x{format_trace_id(span.get_span_context().trace_id)}"
            # initialize span
            span.set_attributes(
                {
                    "framework": "promptflow",
                    "span_type": TraceType.FLOW.value,
                }
            )
            enrich_span_with_context(span)
            # enrich span with input
            enrich_span_with_input(span, inputs)
            yield span

    def _convert_iterators_to_async(self, output: dict):
        for k, v in output.items():
            if isinstance(v, Iterator):
                output[k] = sync_iterator_to_async(v)
        return output

    async def _exec_inner_with_trace_async(
        self,
        inputs: Mapping[str, Any],
        run_info: FlowRunInfo,
        run_tracker: RunTracker,
        context: FlowExecutionContext,
        stream=False,
    ):
        with self._start_flow_span(inputs) as span:
            output, nodes_outputs = await self._traverse_nodes_async(inputs, context)
            output = await self._stringify_generator_output_async(output) if not stream else output
            self._exec_post_process(inputs, output, nodes_outputs, run_info, run_tracker, span, stream)
            return output, extract_aggregation_inputs(self._flow, nodes_outputs)

    def _exec_inner_with_trace(
        self,
        inputs: Mapping[str, Any],
        run_info: FlowRunInfo,
        run_tracker: RunTracker,
        context: FlowExecutionContext,
        stream=False,
    ):
        with self._start_flow_span(inputs) as span:
            output, nodes_outputs = self._traverse_nodes(inputs, context)
            output = self._stringify_generator_output(output) if not stream else output
            self._exec_post_process(inputs, output, nodes_outputs, run_info, run_tracker, span, stream)
            return output, extract_aggregation_inputs(self._flow, nodes_outputs)

    @contextlib.contextmanager
    def _record_cancellation_exceptions_to_span(self, span: Span):
        try:
            yield
        except (KeyboardInterrupt, asyncio.CancelledError) as ex:
            if span.is_recording():
                span.record_exception(ex)
                span.set_status(StatusCode.ERROR, "Execution cancelled.")
            raise

    def _exec_post_process(
        self,
        inputs,
        output,
        nodes_outputs,
        run_info: FlowRunInfo,
        run_tracker: RunTracker,
        span: Span,
        stream: bool,
    ):
        # Persist the node runs for the nodes that have a generator output
        generator_output_nodes = [
            nodename
            for nodename, output in nodes_outputs.items()
            if isinstance(output, Iterator) or isinstance(output, AsyncIterator)
        ]
        # When stream is True, we allow generator output in the flow output
        run_tracker.allow_generator_types = stream
        run_tracker.update_and_persist_generator_node_runs(run_info.run_id, generator_output_nodes)
        run_tracker.end_run(run_info.run_id, result=output)
        if self._tracing_disabled():
            return
        enrich_span_with_trace_type(span, inputs, output, trace_type=TraceType.FLOW)
        span.set_status(StatusCode.OK)

    def _exec(
        self,
        inputs: Mapping[str, Any],
        run_id: Optional[str] = None,
        line_number: Optional[int] = None,
        validate_inputs: bool = False,
        allow_generator_output: bool = False,
    ) -> LineResult:
        """execute line run

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
            index=line_number,
            message_format=self._message_format,
        )
        context = FlowExecutionContext(
            name=self._flow.name,
            run_tracker=run_tracker,
            cache_manager=self._cache_manager,
            run_id=run_id,
            flow_id=self._flow_id,
            line_number=line_number,
            message_format=self._message_format,
        )
        output = {}
        aggregation_inputs = {}
        try:
            if validate_inputs:
                inputs = FlowValidator.ensure_flow_inputs_type(flow=self._flow, inputs=inputs, idx=run_info.index)
            inputs = self._multimedia_processor.load_multimedia_data(self._flow.inputs, inputs)
            # Inputs are assigned after validation and multimedia data loading, instead of at the start of the flow run.
            # This way, if validation or multimedia data loading fails, we avoid persisting invalid inputs.
            run_info.inputs = inputs
            output, aggregation_inputs = self._exec_inner_with_trace(
                inputs,
                run_info,
                run_tracker,
                context,
                allow_generator_output,
            )
        except KeyboardInterrupt as ex:
            # Run will be cancelled when the process receives a SIGINT signal.
            # KeyboardInterrupt will be raised after asyncio finishes its signal handling
            # End run with the KeyboardInterrupt exception, so that its status will be Canceled
            flow_logger.info("Received KeyboardInterrupt, cancel the run.")
            # Update the run info of those running nodes to a canceled status.
            run_tracker.cancel_node_runs(run_id)
            run_tracker.end_run(line_run_id, ex=ex)
        except Exception as ex:
            run_tracker.end_run(line_run_id, ex=ex)
            if self._raise_ex:
                raise
        finally:
            run_tracker._update_flow_run_info_with_node_runs(run_info)
            run_tracker.persist_flow_run(run_info)
        node_run_infos = run_tracker.collect_child_node_runs(line_run_id)
        node_runs = {node_run.node: node_run for node_run in node_run_infos}
        return LineResult(output, aggregation_inputs, run_info, node_runs)

    async def _exec_async(
        self,
        inputs: Mapping[str, Any],
        run_id: Optional[str] = None,
        line_number: Optional[int] = None,
        validate_inputs: bool = False,
        allow_generator_output: bool = False,
    ) -> LineResult:
        """execute line run

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
            message_format=self._message_format,
        )
        context = FlowExecutionContext(
            name=self._flow.name,
            run_tracker=run_tracker,
            cache_manager=self._cache_manager,
            run_id=run_id,
            flow_id=self._flow_id,
            line_number=line_number,
            message_format=self._message_format,
        )
        output = {}
        aggregation_inputs = {}
        try:
            if validate_inputs:
                inputs = FlowValidator.ensure_flow_inputs_type(flow=self._flow, inputs=inputs, idx=run_info.index)
            # TODO: Consider async implementation for load_multimedia_data
            inputs = self._multimedia_processor.load_multimedia_data(self._flow.inputs, inputs)
            # Inputs are assigned after validation and multimedia data loading, instead of at the start of the flow run.
            # This way, if validation or multimedia data loading fails, we avoid persisting invalid inputs.
            run_info.inputs = inputs
            output, aggregation_inputs = await self._exec_inner_with_trace_async(
                inputs,
                run_info,
                run_tracker,
                context,
                allow_generator_output,
            )
        except asyncio.CancelledError as ex:
            flow_logger.info("Received cancelled error, cancel the run.")
            run_tracker.cancel_node_runs(run_id)
            run_tracker.end_run(line_run_id, ex=ex)
            if self._raise_ex:
                raise
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

    def _extract_outputs(self, nodes_outputs, bypassed_nodes, flow_inputs):
        outputs = {}
        for name, output in self._flow.outputs.items():
            if output.reference.value_type == InputValueType.LITERAL:
                outputs[name] = output.reference.value
                continue
            if output.reference.value_type == InputValueType.FLOW_INPUT:
                outputs[name] = flow_inputs[output.reference.value]
                continue
            if output.reference.value_type != InputValueType.NODE_REFERENCE:
                raise NotSupported(
                    message_format=(
                        "The output type '{output_type}' is currently unsupported. "
                        "Please choose from available types: '{supported_output_type}' and try again."
                    ),
                    output_type=(
                        output.reference.value_type.value
                        if hasattr(output.reference.value_type, "value")
                        else output.reference.value_type
                    ),
                    supported_output_type=[output_type.value for output_type in InputValueType],
                )
            node = next((n for n in self._flow.nodes if n.name == output.reference.value), None)
            if not node:
                raise OutputReferenceNotExist(
                    message_format=(
                        "The output '{output_name}' for flow is incorrect. The node '{node_name}' "
                        "referenced by the output '{output_name}' can not found in flow. "
                        "Please rectify the error in your flow and try again."
                    ),
                    node_name=output.reference.value,
                    output_name=name,
                )
            if node.aggregation:
                # Note that the reduce node referenced in the output is not supported.
                continue
            if node.name not in nodes_outputs:
                raise NodeOutputNotFound(
                    message_format=(
                        "The output '{output_name}' for flow is incorrect. "
                        "No outputs found for node '{node_name}'. Please review the problematic "
                        "output and rectify the error."
                    ),
                    output_name=name,
                    node_name=node.name,
                )
            if output.reference.value in bypassed_nodes:
                flow_logger.warning(
                    f"The node referenced by output:'{output.reference.value}' is bypassed, which is not recommended."
                )
            node_result = nodes_outputs[output.reference.value]
            outputs[name] = _input_assignment_parser.parse_node_property(
                output.reference.value, node_result, output.reference.property
            )
        return outputs

    def _should_use_async(self):
        def is_async(f):
            # Here we check the original function since currently asyncgenfunction would be converted to sync func
            # TODO: Improve @trace logic to make sure wrapped asyncgen is still an asyncgen
            original_func = getattr(f, "__original_function", f)
            return inspect.iscoroutinefunction(original_func) or inspect.isasyncgenfunction(original_func)

        return (
            any(is_async(f) for f in self._tools_manager._tools.values())
            or os.environ.get("PF_USE_ASYNC", "false").lower() == "true"
        )

    def _traverse_nodes(self, inputs, context: FlowExecutionContext) -> Tuple[dict, dict]:
        batch_nodes = [node for node in self._flow.nodes if not node.aggregation]
        outputs = {}
        nodes_outputs, bypassed_nodes = self._submit_to_scheduler(context, inputs, batch_nodes)
        outputs = self._extract_outputs(nodes_outputs, bypassed_nodes, inputs)
        return outputs, nodes_outputs

    async def _traverse_nodes_async(self, inputs, context: FlowExecutionContext) -> Tuple[dict, dict]:
        batch_nodes = [node for node in self._flow.nodes if not node.aggregation]
        flow_logger.info("Start executing nodes in async mode.")
        scheduler = AsyncNodesScheduler(self._tools_manager, self._node_concurrency)
        nodes_outputs, bypassed_nodes = await scheduler.execute(batch_nodes, inputs, context, self._line_timeout_sec)
        outputs = self._extract_outputs(nodes_outputs, bypassed_nodes, inputs)
        return outputs, nodes_outputs

    @staticmethod
    async def _merge_async_iterator(async_it: AsyncIterator, outputs: dict, key: str):
        items = []
        async for item in async_it:
            items.append(item)
        outputs[key] = "".join(str(item) for item in items)

    async def _stringify_generator_output_async(self, outputs: dict):
        pool = ThreadPoolExecutorWithContext()
        tasks = []
        for k, v in outputs.items():
            if isinstance(v, AsyncIterator):
                tasks.append(asyncio.create_task(self._merge_async_iterator(v, outputs, k)))
            elif isinstance(v, Iterator):
                loop = asyncio.get_event_loop()
                task = loop.run_in_executor(pool, self._merge_iterator, v, outputs, k)
                tasks.append(task)
        if tasks:
            await asyncio.wait(tasks)
        return outputs

    @staticmethod
    def _merge_iterator(gen: Iterator, outputs: dict, key: str):
        outputs[key] = "".join(str(item) for item in gen)

    def _stringify_generator_output(self, outputs: dict):
        for k, v in outputs.items():
            if isinstance(v, Iterator):
                self._merge_iterator(v, outputs, k)

        return outputs

    def _submit_to_scheduler(self, context: FlowExecutionContext, inputs, nodes: List[Node]) -> Tuple[dict, dict]:
        if not isinstance(self._node_concurrency, int):
            raise UnexpectedError(
                message_format=(
                    "Flow execution failed. To proceed, ensure that a valid node concurrency value is set. "
                    "The current value is {current_value}. Please contact support for further assistance."
                ),
                current_value=self._node_concurrency,
            )
        flow_logger.info("Start executing nodes in thread pool mode.")
        scheduler = FlowNodesScheduler(self._tools_manager, inputs, nodes, self._node_concurrency, context)
        return scheduler.execute(self._line_timeout_sec)

    @staticmethod
    def apply_inputs_mapping(
        inputs: Mapping[str, Mapping[str, Any]],
        inputs_mapping: Mapping[str, str],
    ) -> Dict[str, Any]:
        # TODO: This function will be removed after the batch engine refactoring is completed.
        from promptflow._utils.inputs_mapping_utils import apply_inputs_mapping

        return apply_inputs_mapping(inputs, inputs_mapping)

    def enable_streaming_for_llm_flow(self, stream_required: Callable[[], bool]):
        """Enable the LLM node that is connected to output to return streaming results controlled by `stream_required`.

        If the stream_required callback returns True, the LLM node will return a generator of strings.
        Otherwise, the LLM node will return a string.

        :param stream_required: A callback that takes no arguments and returns a boolean value indicating whether \
        streaming results should be enabled for the LLM node.
        :type stream_required: Callable[[], bool]

        :return: None
        """
        for node in self._flow.nodes:
            streaming_option_parameter = self._parse_streaming_option_parameter(node)
            if (
                streaming_option_parameter is not None
                and self._flow.is_referenced_by_flow_output(node)
                and not self._flow.is_referenced_by_other_node(node)
            ):
                wrapper = _inject_stream_options(stream_required, streaming_option_parameter)
                self._tools_manager.wrap_tool(node.name, wrapper=wrapper)

    def _parse_streaming_option_parameter(self, node: Node) -> Optional[str]:
        if self._flow.is_llm_node(node):
            return "stream"
        tool_function = self._tools_manager.get_tool(node.name)
        return getattr(tool_function, STREAMING_OPTION_PARAMETER_ATTR, None)

    def ensure_flow_is_serializable(self):
        """Ensure that the flow is serializable.

        Some of the nodes may return a generator of strings to create streaming outputs.
        This is useful when the flow is deployed as a web service.
        However, in the interactive mode, the executor assumes that the node result is JSON serializable.

        This method adds a wrapper to each node in the flow
        to consume the streaming outputs and merge them into a string for executor usage.

        :return: None
        """
        for node in self._flow.nodes:
            self._tools_manager.wrap_tool(node.name, wrapper=_ensure_node_result_is_serializable)


def _inject_stream_options(should_stream: Callable[[], bool], streaming_option_parameter="stream"):
    """Inject the stream options to the decorated function.

    AzureOpenAI.completion and AzureOpenAI.chat tools support both stream and non-stream mode.
    The stream mode is controlled by the "stream" parameter.
    """

    def stream_option_decorator(f):
        # We only wrap the function if it has a "stream" parameter
        signature = inspect.signature(f)
        if streaming_option_parameter not in signature.parameters:
            return f

        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            kwargs = kwargs or {}
            kwargs.update({streaming_option_parameter: should_stream()})

            return f(*args, **kwargs)

        return wrapper

    return stream_option_decorator


def enable_streaming_for_llm_tool(f):
    """Enable the stream mode for LLM tools that support it.

    :param f: The function to wrap.
    :type f: function
    :return: The wrapped function.
    :rtype: function

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


def _ensure_node_result_is_serializable(f):
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
        if isinstance(result, Iterator):
            result = "".join(str(trunk) for trunk in result)
        return result

    return wrapper


def execute_flow(
    flow_file: Path,
    working_dir: Path,
    output_dir: Path,
    connections: dict,
    inputs: Mapping[str, Any],
    *,
    run_id: str = None,
    run_aggregation: bool = True,
    enable_stream_output: bool = False,
    allow_generator_output: bool = False,  # TODO: remove this
    init_kwargs: Optional[dict] = None,
    **kwargs,
) -> LineResult:
    """Execute the flow, including aggregation nodes.

    :param flow_file: The path to the flow file.
    :type flow_file: Path
    :param working_dir: The working directory of the flow.
    :type working_dir: Path
    :param output_dir: Relative path relative to working_dir.
    :type output_dir: Path
    :param connections: A dictionary containing connection information.
    :type connections: dict
    :param inputs: A dictionary containing the input values for the flow.
    :type inputs: Mapping[str, Any]
    :param enable_stream_output: Whether to allow stream (generator) output for flow output. Default is False.
    :type enable_stream_output: Optional[bool]
    :param run_id: Run id will be set in operation context and used for session.
    :type run_id: Optional[str]
    :param init_kwargs: Initialization parameters for flex flow, only supported when flow is callable class.
    :type init_kwargs: dict
    :param kwargs: Other keyword arguments to create flow executor.
    :type kwargs: Any
    :return: The line result of executing the flow.
    :rtype: ~promptflow.executor._result.LineResult
    """
    flow_executor = FlowExecutor.create(
        flow_file, connections, working_dir, raise_ex=False, init_kwargs=init_kwargs, **kwargs
    )
    flow_executor.enable_streaming_for_llm_flow(lambda: enable_stream_output)
    with _change_working_dir(working_dir), _force_flush_tracer_provider():
        # Execute nodes in the flow except the aggregation nodes
        # TODO: remove index=0 after UX no longer requires a run id similar to batch runs
        # (run_id_index, eg. xxx_0) for displaying the interface
        line_result = flow_executor.exec_line(
            inputs, index=0, allow_generator_output=allow_generator_output, run_id=run_id
        )
        # persist the output to the output directory
        line_result.output = flow_executor._multimedia_processor.persist_multimedia_data(
            line_result.output, base_dir=working_dir, sub_dir=output_dir
        )
        if run_aggregation and line_result.aggregation_inputs:
            # Convert inputs of aggregation to list type
            flow_inputs = {k: [v] for k, v in inputs.items()}
            aggregation_inputs = {k: [v] for k, v in line_result.aggregation_inputs.items()}
            aggregation_results = flow_executor.exec_aggregation(
                flow_inputs, aggregation_inputs=aggregation_inputs, run_id=run_id
            )
            line_result.node_run_infos = {**line_result.node_run_infos, **aggregation_results.node_run_infos}
            line_result.run_info.metrics = aggregation_results.metrics
            # The aggregation inputs of line results is not utilized in the flow test. So we set it into None.
            line_result.aggregation_inputs = None
        if isinstance(line_result.output, dict):
            # remove line_number from output
            line_result.output.pop(LINE_NUMBER_KEY, None)
        return line_result


@contextmanager
def _force_flush_tracer_provider():
    try:
        yield
    finally:
        try:
            # Force flush the tracer provider to ensure all spans are exported before the process exits.
            tracer_provider = otel_trace.get_tracer_provider()
            if hasattr(tracer_provider, "force_flush"):
                tracer_provider.force_flush()
        except Exception as e:
            flow_logger.warning(f"Error occurred while force flush tracer provider: {e}")


def signal_handler(sig, frame):
    """Handle the terminate signal received by the process.

    Currently, only the single node run use this handler. We print the log and raise a
    KeyboardInterrupt so that external code can catch this exception and cancel the running node."
    """
    logger.info(f"Received signal {sig}({signal.Signals(sig).name}), will terminate the current process.")
    raise KeyboardInterrupt
