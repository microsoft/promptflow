import asyncio
import copy
import functools
import inspect
import os
import uuid
from pathlib import Path
from threading import current_thread
from types import GeneratorType
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from promptflow._constants import LINE_NUMBER_KEY
from promptflow._core._errors import NotSupported, UnexpectedError
from promptflow._core.cache_manager import AbstractCacheManager
from promptflow._core.flow_execution_context import FlowExecutionContext
from promptflow._core.metric_logger import add_metric_logger, remove_metric_logger
from promptflow._core.openai_injector import inject_openai_api
from promptflow._core.operation_context import OperationContext
from promptflow._core.run_tracker import RunTracker
from promptflow._core.tool import STREAMING_OPTION_PARAMETER_ATTR
from promptflow._core.tools_manager import ToolsManager
from promptflow._utils.context_utils import _change_working_dir
from promptflow._utils.execution_utils import (
    apply_default_value_for_input,
    collect_lines,
    get_aggregation_inputs_properties,
)
from promptflow._utils.logger_utils import flow_logger, logger
from promptflow._utils.multimedia_utils import (
    load_multimedia_data,
    load_multimedia_data_recursively,
    persist_multimedia_data,
)
from promptflow._utils.utils import transpose, get_int_env_var
from promptflow._utils.yaml_utils import load_yaml
from promptflow.contracts.flow import Flow, FlowInputDefinition, InputAssignment, InputValueType, Node
from promptflow.contracts.run_info import FlowRunInfo, Status
from promptflow.contracts.run_mode import RunMode
from promptflow.exceptions import PromptflowException
from promptflow.executor import _input_assignment_parser
from promptflow.executor._async_nodes_scheduler import AsyncNodesScheduler
from promptflow.executor._errors import (
    InvalidFlowFileError,
    NodeOutputNotFound,
    OutputReferenceNotExist,
    SingleNodeValidationError
)
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


class BaseExecutor:
    def __init__(
        self,
        flow_file: Path,
        connections: dict,
        *,
        flow_id: Optional[str] = None,
        working_dir: Optional[Path] = None,
        storage: Optional[AbstractRunStorage] = None,
        raise_ex: Optional[bool] = False,
        line_timeout_sec: Optional[int] = None,
    ):
        # Inject OpenAI API to make sure traces and headers injection works and
        # update OpenAI API configs from environment variables.
        inject_openai_api()

        self._flow_file = flow_file
        self._connections = connections
        self._flow_id = flow_id
        self._working_dir = working_dir
        self._storage = storage or DefaultRunStorage()
        self._raise_ex = raise_ex
        self._line_timeout_sec = get_int_env_var("PF_LINE_TIMEOUT_SEC", line_timeout_sec)
        self._log_interval = 60
        # TODO: Improve the experience about configuring node concurrency.
        self._node_concurrency = DEFAULT_CONCURRENCY_BULK

    @classmethod
    def create(
        cls,
        flow_file: Path,
        connections: dict,
        *,
        working_dir: Optional[Path] = None,
        entry: Optional[str] = None,
        storage: Optional[AbstractRunStorage] = None,
        raise_ex: Optional[bool] = True,
        node_override: Optional[Dict[str, Dict[str, Any]]] = None,
        line_timeout_sec: Optional[int] = None,
    ) -> "BaseExecutor":
        from promptflow.executor._script_executor import ScriptExecutor
        from promptflow.executor.flow_executor import FlowExecutor

        if cls._is_eager_flow(flow_file, working_dir):
            if Path(flow_file).suffix.lower() in [".yml", ".yaml"]:
                entry, path = cls._parse_eager_flow_yaml(flow_file, working_dir)
                flow_file = Path(path)
            return ScriptExecutor(
                flow_file=flow_file,
                entry=entry,
                connections=connections,
                working_dir=working_dir,
                storage=storage,
                line_timeout_sec=line_timeout_sec,
            )
        elif Path(flow_file).suffix.lower() in [".yml", ".yaml"]:
            return FlowExecutor.create(
                flow_file=flow_file,
                connections=connections,
                working_dir=working_dir,
                storage=storage,
                raise_ex=raise_ex,
                node_override=node_override,
                line_timeout_sec=line_timeout_sec,
            )
        else:
            raise InvalidFlowFileError(
                message_format="Unsupported flow file type: {flow_file}.", flow_file=flow_file
            )

    @classmethod
    def _is_eager_flow(cls, flow_file: Path, working_dir: Optional[Path] = None):
        if Path(flow_file).suffix.lower() == ".py":
            return True
        elif Path(flow_file).suffix.lower() in [".yaml", ".yml"]:
            flow_file = working_dir / flow_file if working_dir else flow_file
            with open(flow_file, "r", encoding="utf-8") as fin:
                flow_dag = load_yaml(fin)
            if "entry" in flow_dag:
                return True
        return False

    @classmethod
    def _parse_eager_flow_yaml(cls, flow_file: Path, working_dir: Optional[Path] = None):
        flow_file = working_dir / flow_file if working_dir else flow_file
        with open(flow_file, "r", encoding="utf-8") as fin:
            flow_dag = load_yaml(fin)
        return flow_dag.get("entry", ""), flow_dag.get("path", "")

    def _exec_batch_with_process_pool(
        self, batch_inputs: List[dict], run_id, output_dir: Path, validate_inputs: bool = True, variant_id: str = ""
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

        if self._flow_file is None:
            error_message = "flow file is missing"
            raise UnexpectedError(
                message_format=("Unexpected error occurred while init FlowExecutor. Error details: {error_message}."),
                error_message=error_message,
            )

        from ._line_execution_process_pool import LineExecutionProcessPool

        with LineExecutionProcessPool(
            self,
            nlines,
            run_id,
            variant_id,
            validate_inputs,
            output_dir,
        ) as pool:
            result_list = pool.run(zip(line_number, batch_inputs))

        return sorted(result_list, key=lambda r: r.run_info.index)

    def _add_line_results(self, line_results: List[LineResult], run_tracker: RunTracker):
        run_tracker._flow_runs.update({result.run_info.run_id: result.run_info for result in line_results})
        run_tracker._node_runs.update(
            {
                node_run_info.run_id: node_run_info
                for result in line_results
                for node_run_info in result.node_run_infos.values()
            }
        )

def execute_flow(
    flow_file: Path,
    working_dir: Path,
    output_dir: Path,
    connections: dict,
    inputs: Mapping[str, Any],
    *,
    run_aggregation: bool = True,
    enable_stream_output: bool = False,
    allow_generator_output: bool = False,  # TODO: remove this
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
    :param kwargs: Other keyword arguments to create flow executor.
    :type kwargs: Any
    :return: The line result of executing the flow.
    :rtype: ~promptflow.executor._result.LineResult
    """
    flow_executor = BaseExecutor.create(flow_file, connections, working_dir=working_dir, raise_ex=False, **kwargs)
    flow_executor.enable_streaming_for_llm_flow(lambda: enable_stream_output)
    with _change_working_dir(working_dir):
        # execute nodes in the flow except the aggregation nodes
        # TODO: remove index=0 after UX no longer requires a run id similar to batch runs
        # (run_id_index, eg. xxx_0) for displaying the interface
        line_result = flow_executor.exec_line(inputs, index=0, allow_generator_output=allow_generator_output)
        # persist the output to the output directory
        line_result.output = persist_multimedia_data(line_result.output, base_dir=working_dir, sub_dir=output_dir)
        if run_aggregation and line_result.aggregation_inputs:
            # convert inputs of aggregation to list type
            flow_inputs = {k: [v] for k, v in inputs.items()}
            aggregation_inputs = {k: [v] for k, v in line_result.aggregation_inputs.items()}
            aggregation_results = flow_executor.exec_aggregation(flow_inputs, aggregation_inputs=aggregation_inputs)
            line_result.node_run_infos = {**line_result.node_run_infos, **aggregation_results.node_run_infos}
            line_result.run_info.metrics = aggregation_results.metrics
        if isinstance(line_result.output, dict):
            # remove line_number from output
            line_result.output.pop(LINE_NUMBER_KEY, None)
        return line_result
