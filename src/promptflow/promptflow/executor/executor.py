import copy
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, TypeVar

from promptflow._constants import DEFAULT_FLOW_YAML_FILE, PromptflowEdition
from promptflow.contracts.flow import (
    BaseFlowRequest,
    BatchFlowRequest,
    EvalRequest,
    Flow,
    InputAssignment,
    Node,
    NodesRequest,
)
from promptflow.contracts.run_info import FlowRunInfo, Status
from promptflow.contracts.run_mode import RunMode
from promptflow.contracts.runtime import SubmitFlowRequest
from promptflow.contracts.tool import ConnectionType, ToolType
from promptflow.core import AbstractCacheManager, RunTracker
from promptflow.core.api_injector import inject_openai_api
from promptflow.core.connection_manager import ConnectionManager
from promptflow.core.tool import ToolInvoker
from promptflow.core.tools_manager import BuiltinsManager
from promptflow.exceptions import ErrorTarget, ResolveConnectionForFlowError
from promptflow.executor.common import _load_tools_and_update_node_inputs
from promptflow.executor.error_codes import (
    BaselineVariantIdNotFound,
    BaselineVariantInVariants,
    BulkTestIdNotFound,
    ConnectionNotFound,
    DuplicateVariantId,
    EmptyInputError,
    EvaluationFlowNotSupported,
    EvaluationFlowRunIdNotFound,
    InvalidRunMode,
    MissingBulkInputs,
    NoValidOutputLine,
    NumberOfInputsAndOutputsNotEqual,
    RequestTypeNotSupported,
    VariantCountNotMatchWithRunCount,
    VariantIdNotFound,
)
from promptflow.executor.flow_executor import FlowExecutor
from promptflow.executor.flow_request_validator import FlowRequestValidator
from promptflow.executor.nodes_executor import NodesExecutor
from promptflow.executor.nodes_request_validator import NodesRequestValidator
from promptflow.executor.tool_invoker import DefaultToolInvoker
from promptflow.utils.dataclass_serializer import serialize
from promptflow.utils.logger_utils import logger, update_log_path
from promptflow.utils.utils import load_json, reverse_transpose

T = TypeVar("T")


class FlowExecutionCoodinator:
    LINE_NUMBER = "line_number"
    VARIANT_ID = "variant_id"
    VARIANT_IDS = "variant_ids"

    def __init__(
        self,
        builtins_manager: BuiltinsManager,
        cache_manager: AbstractCacheManager,
        run_tracker: RunTracker,
        nthreads: int = 16,
    ):
        inject_openai_api()  # Inject OpenAI API to make sure traces and headers injection works.
        ToolInvoker.activate(DefaultToolInvoker())
        from promptflow.core.metric_logger import add_metric_logger
        from promptflow.core.run_tracker import log_metric

        add_metric_logger(log_metric)
        self._builtins_manager = builtins_manager
        self._cache_manager = cache_manager
        self._run_tracker = run_tracker
        self._storage = self._run_tracker._storage
        self._nthreads = nthreads
        self._connections_in_env = {}
        #  This is for local testing
        if "PROMPTFLOW_CONNECTIONS" in os.environ:
            self._connections_in_env = ConnectionManager.init_from_env().to_connections_dict()

    @staticmethod
    def init_with_run_tracker(run_tracker) -> "FlowExecutionCoodinator":
        builtins_manager = BuiltinsManager()
        cache_manager = AbstractCacheManager.init_from_env()
        return FlowExecutionCoodinator(
            builtins_manager=builtins_manager,
            cache_manager=cache_manager,
            run_tracker=run_tracker,
        )

    @staticmethod
    def init_from_env() -> "FlowExecutionCoodinator":
        builtins_manager = BuiltinsManager()
        cache_manager = AbstractCacheManager.init_from_env()
        run_tracker = RunTracker.init_from_env()
        return FlowExecutionCoodinator(
            builtins_manager=builtins_manager,
            cache_manager=cache_manager,
            run_tracker=run_tracker,
        )

    @staticmethod
    def apply_flow_overrides(flow, node_overrides):
        if not node_overrides:
            return flow
        # We don't do detailed error handling here, since it should never fail
        for key, value in node_overrides.items():
            node_name, input_name = key.split(".")
            node = flow.get_node(node_name)
            if node is None:
                raise ValueError(f"Cannot find node {node_name} in flow {flow.name}")
            # For LLM node, here we override the connection field in node
            if node.connection and input_name == "connection":
                node.connection = value
            # Other scenarios we override the input value of the inputs
            else:
                node.inputs[input_name] = InputAssignment(value=value)
        return flow

    def create_flow_executor_by_yaml(
        self,
        yaml_file: Path,
        connections: dict,
        working_dir: Optional[Path] = None,
        node_overrides: Optional[Dict[str, str]] = None,
    ):
        flow = Flow.from_yaml(yaml_file, working_dir=working_dir)
        flow = self.apply_flow_overrides(flow, node_overrides)
        flow = FlowRequestValidator.ensure_flow_valid(flow, connections)
        return self.create_flow_executor(flow, connections, raise_ex=True)

    def create_nodes_executor_by_yaml(
        self,
        yaml_file: Path,
        node_name: str,
        node_input: dict,
        connections: dict,
        working_dir: Optional[Path] = None,
    ):
        flow = Flow.from_yaml(yaml_file, working_dir=working_dir)
        single_node = NodesRequestValidator.ensure_single_node(flow, node_name, connections)
        NodesRequestValidator.ensure_single_node_inputs(flow, single_node, node_input)
        flow.nodes = [single_node]
        return self.create_nodes_executor(flow, connections, raise_ex=True)

    @staticmethod
    def _resolve_flow_file(flow_file: Path):
        flow_file = Path(flow_file)
        if flow_file.is_dir():
            if (flow_file / DEFAULT_FLOW_YAML_FILE).exists():
                flow_file = flow_file / DEFAULT_FLOW_YAML_FILE
            # For backward compatibility to support json flow file, will be deprecated
            elif (flow_file / "flow.json").exists():
                flow_file = flow_file / "flow.json"
            else:
                raise FileNotFoundError(f"Cannot find flow file in {flow_file}")
        return flow_file

    @staticmethod
    def get_connection_names_from_node_overrides(flow_file: Path, node_overrides: Dict[str, str]):
        flow_file = FlowExecutionCoodinator._resolve_flow_file(flow_file)
        if flow_file.suffix == ".json":
            flow = Flow.deserialize(load_json(flow_file))
        else:
            flow = Flow.from_yaml(flow_file)
        connection_names = set()
        for key, value in node_overrides.items():
            node_name, input_name = key.split(".")
            node = flow.get_node(node_name)
            if node is None:
                raise ValueError(f"Cannot find node {node_name} in flow {flow.name}")
            if node.type == ToolType.LLM:
                if input_name == "connection":
                    connection_names.add(value)
            elif node.type == ToolType.PYTHON:
                tool_spec = flow.get_tool(node.tool)
                if tool_spec is None:
                    raise ValueError(f"Cannot find tool {node.tool} in flow {flow.name}")
                tool_input = tool_spec.inputs[input_name]
                for tool_type in tool_input.type:
                    if isinstance(tool_type, str) and ConnectionType.is_connection_class_name(tool_type):
                        connection_names.add(value)
                        break
        return connection_names

    def create_flow_executor_by_model(
        self,
        flow_file: Path,
        connections: dict,
        node_overrides: Optional[Dict[str, str]] = None,
    ):
        """Here we assume all the tools are in the same directory as the flow file."""
        flow_file = self._resolve_flow_file(flow_file)
        if flow_file.suffix == ".json":
            # For backward compatibility to support json flow file
            return self._create_flow_executor_by_json(flow_file, connections, node_overrides=node_overrides)
        return self.create_flow_executor_by_yaml(flow_file, connections, node_overrides=node_overrides)

    def _create_flow_executor_by_json(self, flow_file: Path, connections: dict, node_overrides):
        model_dir = flow_file.resolve().parent
        flow = Flow.deserialize(load_json(flow_file))
        flow = self.apply_flow_overrides(flow, node_overrides)
        # Connection required modules will be imported after ensure flow valid
        flow = FlowRequestValidator.ensure_flow_valid(flow, connections)
        for tool in flow.tools:
            if tool.source and not tool.code:
                tool.code = (model_dir / tool.source).read_text(encoding="utf-8")
        return self.create_flow_executor(flow, connections, raise_ex=True)

    def create_flow_executor(self, flow: Flow, connections: dict, is_bulk_test=False, raise_ex=False):
        loaded_tools = _load_tools_and_update_node_inputs(flow)
        return FlowExecutor(
            flow=flow,
            connections=connections,
            run_tracker=self._run_tracker,
            cache_manager=self._cache_manager,
            loaded_tools=loaded_tools,
            nthreads=self._nthreads,
            is_bulk_test=is_bulk_test,
            raise_ex=raise_ex,
        )

    def create_nodes_executor(self, flow: Flow, connections: dict, raise_ex=False):
        loaded_tools = _load_tools_and_update_node_inputs(flow)
        return NodesExecutor(
            flow=flow,
            connections=connections,
            run_tracker=self._run_tracker,
            cache_manager=self._cache_manager,
            loaded_tools=loaded_tools,
            raise_ex=raise_ex,
        )

    @classmethod
    def get_bulk_test_variants_run_ids(cls, req: SubmitFlowRequest):
        """Get all variants run ids for bulk test"""
        run_ids = []
        if isinstance(req.submission_data, BatchFlowRequest):
            if req.submission_data.variants_runs:
                run_ids = list(req.submission_data.variants_runs.values())
        return run_ids

    @classmethod
    def get_root_run_ids(cls, req: SubmitFlowRequest):
        """Get all root run ids includes variant and evaluation runs except the shell(parent run)"""
        root_run_ids = [req.flow_run_id]
        if isinstance(req.submission_data, BatchFlowRequest):
            #  Variants
            root_run_ids += cls.get_bulk_test_variants_run_ids(req=req)
            # Evaluation
            if req.submission_data.eval_flow and req.submission_data.eval_flow_run_id:
                root_run_ids.append(req.submission_data.eval_flow_run_id)
        return root_run_ids

    def end_bulk_test_aml_run(self, raw_request: SubmitFlowRequest, run_tracker):
        """End the bulk test aml run that gets pre-created by MT"""
        bulk_test_id = raw_request.submission_data.bulk_test_id

        if not bulk_test_id:
            raise BulkTestIdNotFound(
                message="Failed to get bulk test id when trying to end bulk test aml run. Please check the request.",
            )

        run_tracker.end_bulk_test_aml_run(bulk_test_id)

    def exec_request_raw(self, raw_request: SubmitFlowRequest, raise_ex=False):
        """Execute the request and return the result"""
        if not isinstance(raw_request, SubmitFlowRequest):
            raise RequestTypeNotSupported(
                message=f"Raw request must be 'SubmitFlowRequest' type, got {type(raw_request)!r}.",
            )

        self._run_tracker._activate_in_context()
        try:
            with self._run_tracker.node_log_manager:
                # enrich run tracker with the run mode, to determine if we need to update run history
                self._run_tracker._run_mode = raw_request.run_mode
                self._ensure_submission_data(raw_request.submission_data, raw_request.run_mode)
                return self._route_request_raw(raw_request, raise_ex=raise_ex)
        except Exception as ex:
            logger.exception(f"Submission request failed. Exception: {ex}")
            root_run_ids = raw_request.get_root_run_ids()
            self._run_tracker.mark_notstarted_runs_as_failed(raw_request.flow_id, root_run_ids, ex)
            raise
        finally:
            self._run_tracker._deactivate_in_context()
            # if this is a bulk test and it's enterprise edition, we need to end the aml run that get created by MT
            if self._run_tracker.is_bulk_test and self._run_tracker._storage._edition == PromptflowEdition.ENTERPRISE:
                self.end_bulk_test_aml_run(raw_request=raw_request, run_tracker=self._run_tracker)

    def _ensure_submission_data(self, data: BaseFlowRequest, run_mode: RunMode):
        # Get the required connection name.
        try:
            if isinstance(data, NodesRequest):
                # Get the required connection for current node or current and afterwards nodes.
                required_connections = data.get_node_connection_names(run_mode)
            else:
                # Get required connection for the whole flow.
                required_connections = data.flow.get_connection_names()
        except Exception as ex:
            raise ResolveConnectionForFlowError(
                message=f"{ex}",
                target=ErrorTarget.EXECUTOR,
            ) from ex
        # Ensure the connection names are valid.
        connections = data.connections or {}
        for connection in required_connections:
            if connection not in connections:
                if connection not in self._connections_in_env:
                    raise ConnectionNotFound(
                        message=f"Connection '{connection}' is not found, "
                        f"available connection keys {list(connections.keys())}.",
                    )
                connections[connection] = self._connections_in_env[connection]
        data.connections = connections
        return data

    def _assert_bulktest_request(self, req: BatchFlowRequest):
        if not req.bulk_test_id:
            raise BulkTestIdNotFound(message="Bulk test ID is not set for bulk test.")
        if not req.baseline_variant_id:
            raise BaselineVariantIdNotFound(message="Baseline variant ID is not set for bulk test.")
        if req.eval_flow:
            if not req.eval_flow_run_id:
                raise EvaluationFlowRunIdNotFound(message="Evaluation flow run ID is not set for bulk test.")
        if req.variants:
            if set(req.variants.keys()) != set(req.variants_runs.keys()):
                raise VariantCountNotMatchWithRunCount(message="Variants and variants runs do not match for bulk test.")

    def _route_request_raw(self, raw_request: SubmitFlowRequest, raise_ex=False):
        run_mode = raw_request.run_mode
        request = raw_request.submission_data

        if run_mode in (RunMode.Flow, run_mode.BulkTest):
            assert isinstance(request, BatchFlowRequest)
            if not request.batch_inputs:
                raise EmptyInputError(
                    message=f"Inputs in the request of flow '{request.flow.name}' is empty.",
                )
            if run_mode == run_mode.BulkTest:
                self._assert_bulktest_request(request)
            else:
                # If it is a normal flow run, clear bulk test related fields
                request.bulk_test_id = None
                request.eval_flow_run_id = None
                request.eval_flow = None
                request.eval_flow_inputs_mapping = None
            if run_mode == run_mode.Flow and request.eval_flow:
                raise EvaluationFlowNotSupported(
                    message="Evaluation flow is only allowed for bulk test mode.",
                )
            return self._exec_batch_request(
                flow_run_id=raw_request.flow_run_id,
                source_run_id=raw_request.source_flow_run_id,
                flow_id=raw_request.flow_id,
                batch_request=request,
                run_id_to_log_path=raw_request.run_id_to_log_path,
                raise_ex=raise_ex,
            )
        elif run_mode == RunMode.Eval:
            assert isinstance(request, EvalRequest)
            return self._exec_eval_request(
                flow_run_id=raw_request.flow_run_id,
                source_run_id=raw_request.source_flow_run_id,
                eval_request=request,
                run_id_to_log_path=raw_request.run_id_to_log_path,
                raise_ex=raise_ex,
            )
        elif run_mode == RunMode.SingleNode or run_mode == RunMode.FromNode:
            assert isinstance(request, NodesRequest)
            return self._exec_nodes_request(request, run_mode, raise_ex)
        else:
            raise InvalidRunMode(message=f"Invalid run_mode value: {run_mode}")

    def _exec_eval_request(
        self,
        flow_run_id: str,
        source_run_id: str,
        eval_request: EvalRequest,
        run_id_to_log_path: Dict[str, str] = None,
        raise_ex: bool = False,
    ):
        run_infos = [
            self._storage.get_flow_run(
                run_id,
                eval_request.bulk_test_flow_id,
            )
            for run_id in eval_request.bulk_test_flow_run_ids
        ]
        variant_ids = []
        for run_id, run_info in zip(eval_request.bulk_test_flow_run_ids, run_infos):
            if run_info is None:
                raise EvaluationFlowRunIdNotFound(message=f"Flow run {run_id} is not found.")
            if not run_info.variant_id:
                raise VariantIdNotFound(message=f"Flow run {run_id} does not have a variant id.")
            if run_info.variant_id in variant_ids:
                raise DuplicateVariantId(message=f"Duplicate variant id {run_info.variant_id} found.")
            variant_ids.append(run_info.variant_id)

        variants_outputs = self._collect_variants_outputs(run_infos)
        return self._exec_eval(
            #  Note that here we need to use the flow id of the bulk test flow
            eval_request.bulk_test_flow_id,
            flow_run_id,
            source_run_id,
            eval_request.flow,
            eval_request.bulk_test_id,
            eval_request.bulk_test_inputs,
            variant_ids=variant_ids,
            variants_outputs=variants_outputs,
            inputs_mapping=eval_request.inputs_mapping,
            connections=eval_request.connections,
            run_id_to_log_path=run_id_to_log_path,
            raise_ex=raise_ex,
        )

    def _exec_batch_request(
        self,
        flow_run_id: str,
        source_run_id: str,
        flow_id: str,
        batch_request: BatchFlowRequest,
        run_id_to_log_path: Dict[str, str] = None,
        raise_ex: bool = False,
    ):
        # For evaluation flow
        connections = {k: v for k, v in batch_request.connections.items()} if batch_request.connections else {}
        connections.update(self._connections_in_env)
        run_infos = self._exec_batch_request_inner(
            flow_run_id,
            source_run_id,
            flow_id,
            batch_request,
            run_id_to_log_path,
            raise_ex,
        )
        flow_runs = []
        node_runs = []
        for run_info in run_infos:
            flow_runs.extend(self._run_tracker.collect_flow_runs(run_info.run_id))
            node_runs.extend(self._run_tracker.collect_node_runs(run_info.run_id))
        for flow_run in flow_runs:
            flow_run.request = None  # Remove request to reduce payload size.
        batch_result: dict = {
            "flow_runs": [serialize(run) for run in flow_runs],
            "node_runs": [serialize(run) for run in node_runs],
        }
        successful = all(run_info.status == Status.Completed for run_info in run_infos)
        if batch_request.eval_flow and successful:
            variants_outputs = self._collect_variants_outputs(run_infos)
            variant_ids = [run_info.variant_id for run_info in run_infos]
            batch_inputs = batch_request.batch_inputs
            batch_result["evaluation"] = self._exec_eval(
                flow_id,  # Note that here we should use the flow id of main flow
                batch_request.eval_flow_run_id,
                flow_run_id,
                batch_request.eval_flow,
                batch_request.bulk_test_id,
                batch_inputs,
                variant_ids,
                variants_outputs,
                inputs_mapping=batch_request.eval_flow_inputs_mapping,
                connections=connections,
                run_id_to_log_path=run_id_to_log_path,
                raise_ex=raise_ex,
            )
        return batch_result

    def _collect_variants_outputs(self, variants_runs: List[FlowRunInfo]):
        outputs = {run.variant_id: reverse_transpose(run.output) for run in variants_runs}
        return outputs

    def _get_eval_lines(
        self,
        inputs: dict,
        line_number,
        inputs_mapping,
        variant_ids,
        variants_outputs,
    ) -> List[dict]:
        items = []
        for variant in variant_ids:
            item = FlowExecutor.apply_inputs_mapping_legacy(
                {"data": inputs, "output": variants_outputs[variant]},
                inputs_mapping,
            )
            item[self.VARIANT_ID] = variant
            item[self.LINE_NUMBER] = line_number
            items.append(item)
        return items

    def _get_eval_collection_line(
        self,
        inputs: dict,
        line_number,
        inputs_mapping,
        variant_ids,
        output_names,
        variants_outputs,
    ) -> dict:
        outputs = {
            output_name: [variants_outputs[variant][output_name] for variant in variant_ids]
            for output_name in output_names
        }
        item = FlowExecutor.apply_inputs_mapping_legacy({"data": inputs, "output": outputs}, inputs_mapping)
        item[self.LINE_NUMBER] = line_number
        item[self.VARIANT_IDS] = variant_ids
        return item

    def _construct_eval_batch_inputs(
        self,
        original_inputs,
        variant_ids: List[str],
        variants_outputs,
        inputs_mapping: Mapping[str, str],
        collection_mode=False,
    ) -> List[Dict[str, Any]]:
        batch_inputs = []
        ignored_mappings = {self.LINE_NUMBER, self.VARIANT_ID, self.VARIANT_IDS}
        inputs_mapping = {k: v for k, v in inputs_mapping.items()}
        for key in ignored_mappings:
            if key in inputs_mapping:
                logger.warning(f"Input mapping key '{key}' is reserved and cannot be used.")
                inputs_mapping.pop(key)
        output_names = list(variants_outputs[variant_ids[0]][0].keys())
        # Fallback logic if no inputs mapping is provided
        if not inputs_mapping:
            inputs_mapping = {output_name: "output." + output_name for output_name in output_names}
            inputs_mapping.update({k: "data." + k for k in original_inputs[0].keys()})
        output_count = len(variants_outputs[variant_ids[0]])
        if output_count != len(original_inputs):
            # TODO: Should be system error?
            raise NumberOfInputsAndOutputsNotEqual(
                message=f"Number of inputs and outputs are not equal, inputs: {len(original_inputs)}, "
                "outputs: {output_count}.",
            )
        for idx, i in enumerate(original_inputs):
            output_line = {variant: variants_outputs[variant][idx] for variant in variant_ids}
            # If any variant has all None values, which means it fails in the line, skip this line
            # Only the lines that all variants have outputs will be used for evaluation
            if any(all(v is None for v in output.values()) for output in output_line.values()):
                continue
            if collection_mode:
                line = self._get_eval_collection_line(i, idx, inputs_mapping, variant_ids, output_names, output_line)
                batch_inputs.append(line)
            else:
                lines = self._get_eval_lines(i, idx, inputs_mapping, variant_ids, output_line)
                batch_inputs.extend(lines)
        if not batch_inputs:
            raise NoValidOutputLine(
                message=f"There is no valid output line for evaluation in {len(original_inputs)} input lines,"
                " this may be caused by failed lines in variants, please check the outputs of the variants.",
            )
        return batch_inputs

    def _is_eval_collection_mode(self, flow: Flow) -> bool:
        return "variant_ids" in flow.inputs

    def _exec_eval(
        self,
        flow_id: str,
        flow_run_id: str,
        source_run_id: str,
        flow: Flow,
        bulk_test_id: str,
        bulk_test_inputs,
        variant_ids: List[str],
        variants_outputs: dict,
        inputs_mapping: dict,
        connections: dict,
        run_id_to_log_path: Dict[str, str] = None,
        raise_ex=False,
    ) -> dict:
        if not bulk_test_inputs:
            raise MissingBulkInputs(
                message="Bulk test inputs is not provided for evaluation request.",
            )
        collection_mode = self._is_eval_collection_mode(flow)
        batch_inputs = self._construct_eval_batch_inputs(
            bulk_test_inputs, variant_ids, variants_outputs, inputs_mapping, collection_mode
        )
        batch_request = BatchFlowRequest(flow, connections, batch_inputs=batch_inputs, bulk_test_id=bulk_test_id)
        return self._exec_batch_request(
            flow_run_id, source_run_id, flow_id, batch_request, run_id_to_log_path, raise_ex
        )

    def _exec_nodes_request(self, request: NodesRequest, run_mode: RunMode, raise_ex=False):
        """Execute single node or from a certain node.
        Will not create flow run.
        """
        if not request.variants:
            return self._exec_nodes_request_inner(request, run_mode, raise_ex)
        else:
            return self._exec_nodes_variant_request(request, run_mode, raise_ex)

    def _exec_nodes_variant_request(self, request: NodesRequest, run_mode: RunMode, raise_ex=False):
        if run_mode == RunMode.FromNode:
            raise NotImplementedError("Variants are not supported for FromNode mode.")

        # Among all variants, get the variant which contains the request.node_name.
        # If not found, execute base line node.
        # If more than one variant found, execute the first variant.
        variant_ids = [id for id, nodes in request.variants.items() if request.node_name in set(n.name for n in nodes)]
        if len(variant_ids) == 0:
            logger.warning(f"No variant for node {request.node_name}. Execute base line node.")
            return self._exec_nodes_request_inner(request, run_mode, raise_ex)

        if len(variant_ids) > 1:
            logger.warning(
                f"Expect only 1 variant for node {request.node_name}, Got {len(variant_ids)}. \
                            Only execute variant {variant_ids[0]}"
            )
        variant_id = variant_ids[0]
        variant_nodes = request.variants.get(variant_id)

        # Update flow in request.
        updated_flow = self._replace_flow(
            request.flow,
            variant_nodes,
            request.variants_tools,
        )
        request.flow = updated_flow
        return self._exec_nodes_request_inner(request, run_mode, raise_ex, variant_id)

    def _exec_nodes_request_inner(self, request: NodesRequest, run_mode: RunMode, raise_ex=False, variant_id: str = ""):
        node_inputs = request.node_inputs
        flow = request.flow
        if run_mode == RunMode.SingleNode:
            single_node = NodesRequestValidator.ensure_single_node(flow, request.node_name, request.connections)
            node_inputs = NodesRequestValidator.ensure_single_node_inputs(flow, single_node, node_inputs)
            # Only keep the single node in flow.
            flow.nodes = [single_node]

        if run_mode == RunMode.FromNode:
            # TODO: Add specific validator for from node.
            flow = FlowRequestValidator.ensure_flow_valid(flow, request.connections)

        worker = self.create_nodes_executor(
            flow,
            request.connections,
            raise_ex,
        )

        worker.exec_nodes(
            node_inputs,
            run_mode,
            request.node_name,
            variant_id,
        )

        node_runs = self._run_tracker.collect_node_runs()
        return {
            "flow_runs": None,
            "node_runs": [serialize(run) for run in node_runs],
        }

    def _replace_flow(self, flow: Flow, variant_nodes: List[Node], variant_tools: list):
        new_nodes = []
        nodes_by_name = {n.name: n for n in variant_nodes}
        for node in flow.nodes:
            if node.name in nodes_by_name:
                new_nodes.append(nodes_by_name[node.name])
            else:
                new_nodes.append(copy.deepcopy(node))
        return Flow(
            id=flow.id,
            name=flow.name,
            nodes=new_nodes,
            inputs=flow.inputs,
            outputs=flow.outputs,
            tools=flow.tools + variant_tools,
        )

    def _exec_batch_request_inner(
        self,
        flow_run_id: str,
        source_run_id: str,
        flow_id: str,
        batch_request: BatchFlowRequest,
        run_id_to_log_path: Dict[str, str] = None,
        raise_ex: bool = False,
    ) -> List[FlowRunInfo]:
        flow = FlowRequestValidator.ensure_flow_valid(batch_request.flow, batch_request.connections)
        variants = FlowRequestValidator.ensure_variants_valid(
            batch_request.variants,
            variants_tools=batch_request.variants_tools,
            flow=flow,
            connections=batch_request.connections,
        )
        batch_inputs = FlowRequestValidator.ensure_batch_inputs_type(batch_request.flow, batch_request.batch_inputs)

        baseline_variant_id = batch_request.baseline_variant_id
        if baseline_variant_id in variants:
            msg = f"Baseline variant id '{baseline_variant_id}' should not be in variants."
            raise BaselineVariantInVariants(message=msg)

        run_infos = []
        connections = batch_request.connections
        batch_request.connections = None  # Remove the connections to avoid store it in the DB
        batch_request.flow = flow
        # When execute the flow, the flow will be modified, so we need to make a copy of the flow.
        # TODO: do not modify the flow when execute it.
        original_flow = copy.deepcopy(flow)
        baseline_run_info = self._exec_flow_with_inputs(
            flow_id,
            flow,
            batch_inputs,
            connections,
            run_id=flow_run_id,
            root_run_id=flow_run_id,
            parent_run_id=batch_request.bulk_test_id or "",
            source_run_id=source_run_id,
            variant_id=baseline_variant_id,
            request=batch_request,
            is_bulk_test=batch_request.bulk_test_id is not None,
            run_id_to_log_path=run_id_to_log_path,
            raise_ex=raise_ex,
        )
        run_infos.append(baseline_run_info)
        if not variants:
            return run_infos

        for variant_id, variant_nodes in variants.items():
            updated_flow = self._replace_flow(
                original_flow,
                variant_nodes,
                batch_request.variants_tools,
            )
            batch_request.flow = updated_flow
            flow_run_id = batch_request.variants_runs[variant_id]
            variant_run_info = self._exec_flow_with_inputs(
                flow_id,
                updated_flow,
                batch_inputs,
                connections,
                flow_run_id,
                root_run_id=flow_run_id,
                parent_run_id=batch_request.bulk_test_id or "",
                request=batch_request,
                variant_id=variant_id,
                source_run_id=source_run_id,
                is_bulk_test=True,
                run_id_to_log_path=run_id_to_log_path,
                raise_ex=raise_ex,
            )
            run_infos.append(variant_run_info)
        return run_infos

    def _exec_flow_with_inputs(
        self,
        flow_id: str,
        flow: Flow,  # Flow
        batch_inputs: List,
        connections: dict,  # Request
        run_id: str,
        root_run_id: str,  # Must have fields
        parent_run_id: str = "",
        source_run_id: str = "",
        request=None,  # Optional fields
        variant_id: str = "",  # Variant fields
        is_bulk_test=False,
        run_id_to_log_path: Dict[str, str] = None,
        raise_ex: bool = False,
    ):
        batch_flow_run_info = self._run_tracker.start_root_flow_run(
            flow_id=flow_id,
            root_run_id=root_run_id,
            run_id=run_id,
            parent_run_id=parent_run_id,
        )
        batch_flow_run_info.variant_id = variant_id
        if source_run_id:
            batch_flow_run_info.source_run_id = source_run_id
        if request:  # For the scenario that we don't have variants, we save the request in this run
            batch_flow_run_info.request = request
            batch_flow_run_info.request.connections = None  # Don't save connections
            # If the name/description/tags are not set, we use the ones from the request
            batch_flow_run_info.name = batch_flow_run_info.name or request.name
            batch_flow_run_info.description = batch_flow_run_info.description or request.description
            batch_flow_run_info.tags = batch_flow_run_info.tags or request.tags

        if run_id_to_log_path:
            log_path = run_id_to_log_path.get(run_id)
            if log_path:
                update_log_path(log_path)

        executor = None
        try:
            executor: FlowExecutor = self.create_flow_executor(
                flow,
                connections=connections,
                is_bulk_test=is_bulk_test,
                raise_ex=raise_ex,
            )
            executor.ensure_flow_is_serializable()
            result = executor.exec_batch(
                batch_inputs,
                batch_flow_run_info,
            )
            self._run_tracker.end_run(batch_flow_run_info.run_id, result=result)
        except Exception as e:
            logger.exception(f"Failed to execute flow. Exception: {e}")
            self._run_tracker.end_run(batch_flow_run_info.run_id, ex=e)
            if raise_ex:
                raise
        finally:
            if executor is not None:
                status_summary = executor.get_status_summary(batch_flow_run_info.run_id)
                self._run_tracker.persist_status_summary(status_summary, batch_flow_run_info.run_id)
            self._run_tracker.update_flow_run_info(batch_flow_run_info)
        return batch_flow_run_info
