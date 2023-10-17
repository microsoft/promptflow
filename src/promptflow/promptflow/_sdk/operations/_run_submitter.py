# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# this file is a middle layer between the local SDK and executor, it'll have some similar logic with cloud PFS.

import contextlib
import datetime
import os
import shutil
import tempfile
from os import PathLike
from pathlib import Path

import yaml
from dotenv import load_dotenv

from promptflow._sdk._constants import (
    DAG_FILE_NAME,
    DEFAULT_ENCODING,
    DEFAULT_VAR_ID,
    INPUTS,
    NODE,
    NODE_VARIANTS,
    NODES,
    SUPPORTED_CONNECTION_FIELDS,
    USE_VARIANTS,
    VARIANTS,
    ConnectionFields,
    FlowRunProperties,
)
from promptflow._sdk._errors import InvalidFlowError
from promptflow._sdk._load_functions import load_flow
from promptflow._sdk._logger_factory import LoggerFactory
from promptflow._sdk._utils import (
    _get_additional_includes,
    _merge_local_code_and_additional_includes,
    get_local_connections_from_executable,
    get_used_connection_names_from_dict,
    parse_variant,
    update_dict_value_with_connections,
)
from promptflow._sdk.entities._flow import Flow
from promptflow._sdk.entities._run import Run
from promptflow._sdk.operations._local_storage_operations import LocalStorageOperations
from promptflow._sdk.operations._run_operations import RunOperations
from promptflow._utils.context_utils import _change_working_dir
from promptflow.contracts.flow import Flow as ExecutableFlow
from promptflow.contracts.run_info import Status
from promptflow.contracts.run_mode import RunMode
from promptflow.exceptions import UserErrorException
from promptflow.executor import BatchEngine, FlowExecutor

logger = LoggerFactory.get_logger(name=__name__)


def _load_flow_dag(flow_path: Path):
    if flow_path.is_dir():
        flow_path = flow_path / DAG_FILE_NAME
    if not flow_path.exists():
        raise FileNotFoundError(f"Flow file {flow_path} not found")

    with open(flow_path, "r", encoding=DEFAULT_ENCODING) as f:
        flow_dag = yaml.safe_load(f)
    return flow_path, flow_dag


def overwrite_variant(flow_path: Path, tuning_node: str = None, variant: str = None, drop_node_variants: bool = False):
    flow_path, flow_dag = _load_flow_dag(flow_path=flow_path)

    # check tuning_node & variant
    node_name_2_node = {node["name"]: node for node in flow_dag[NODES]}

    if tuning_node and tuning_node not in node_name_2_node:
        raise InvalidFlowError(f"Node {tuning_node} not found in flow")
    if tuning_node and variant:
        try:
            flow_dag[NODE_VARIANTS][tuning_node][VARIANTS][variant]
        except KeyError as e:
            raise InvalidFlowError(f"Variant {variant} not found for node {tuning_node}") from e
    try:
        node_variants = flow_dag.pop(NODE_VARIANTS, {}) if drop_node_variants else flow_dag.get(NODE_VARIANTS, {})
        updated_nodes = []
        for node in flow_dag.get(NODES, []):
            if not node.get(USE_VARIANTS, False):
                updated_nodes.append(node)
                continue
            # update variant
            node_name = node["name"]
            if node_name not in node_variants:
                raise InvalidFlowError(f"No variant for the node {node_name}.")
            variants_cfg = node_variants[node_name]
            variant_id = variant if node_name == tuning_node else None
            if not variant_id:
                if DEFAULT_VAR_ID not in variants_cfg:
                    raise InvalidFlowError(f"Default variant id is not specified for {node_name}.")
                variant_id = variants_cfg[DEFAULT_VAR_ID]
            if variant_id not in variants_cfg.get(VARIANTS, {}):
                raise InvalidFlowError(f"Cannot find the variant {variant_id} for {node_name}.")
            variant_cfg = variants_cfg[VARIANTS][variant_id][NODE]
            updated_nodes.append({"name": node_name, **variant_cfg})
        flow_dag[NODES] = updated_nodes
    except KeyError as e:
        raise KeyError("Failed to overwrite tuning node with variant") from e

    with open(flow_path, "w", encoding=DEFAULT_ENCODING) as f:
        yaml.safe_dump(flow_dag, f)


def overwrite_connections(flow_path: Path, connections: dict, working_dir: PathLike = None):
    if not connections:
        return
    if not isinstance(connections, dict):
        raise InvalidFlowError(f"Invalid connections overwrite format: {connections}, only list is supported.")

    flow_path, flow_dag = _load_flow_dag(flow_path=flow_path)
    # Load executable flow to check if connection is LLM connection
    executable_flow = ExecutableFlow.from_yaml(flow_file=flow_path, working_dir=working_dir)

    node_name_2_node = {node["name"]: node for node in flow_dag[NODES]}

    for node_name, connection_dict in connections.items():
        if node_name not in node_name_2_node:
            raise InvalidFlowError(f"Node {node_name} not found in flow")
        if not isinstance(connection_dict, dict):
            raise InvalidFlowError(f"Invalid connection overwrite format: {connection_dict}, only dict is supported.")
        node = node_name_2_node[node_name]
        executable_node = executable_flow.get_node(node_name=node_name)
        if executable_flow.is_llm_node(executable_node):
            unsupported_keys = connection_dict.keys() - SUPPORTED_CONNECTION_FIELDS
            if unsupported_keys:
                raise InvalidFlowError(
                    f"Unsupported llm connection overwrite keys: {unsupported_keys},"
                    f" only {SUPPORTED_CONNECTION_FIELDS} are supported."
                )
            try:
                connection = connection_dict.get(ConnectionFields.CONNECTION)
                if connection:
                    node[ConnectionFields.CONNECTION] = connection
                deploy_name = connection_dict.get(ConnectionFields.DEPLOYMENT_NAME)
                if deploy_name:
                    node[INPUTS][ConnectionFields.DEPLOYMENT_NAME] = deploy_name
            except KeyError as e:
                raise KeyError(f"Failed to overwrite llm node {node_name} with connections {connections}") from e
        else:
            connection_inputs = executable_flow.get_connection_input_names_for_node(node_name=node_name)
            for c, v in connection_dict.items():
                if c not in connection_inputs:
                    raise InvalidFlowError(f"Connection with name {c} not found in node {node_name}'s inputs")
                node[INPUTS][c] = v

    with open(flow_path, "w", encoding=DEFAULT_ENCODING) as f:
        yaml.safe_dump(flow_dag, f)


def remove_additional_includes(flow_path: Path):
    flow_path, flow_dag = _load_flow_dag(flow_path=flow_path)
    flow_dag.pop("additional_includes", None)
    with open(flow_path, "w", encoding=DEFAULT_ENCODING) as f:
        yaml.safe_dump(flow_dag, f)


@contextlib.contextmanager
def variant_overwrite_context(
    flow_path: Path,
    tuning_node: str = None,
    variant: str = None,
    connections: dict = None,
    *,
    drop_node_variants: bool = False,
):
    """Override variant and connections in the flow."""
    # TODO: unify variable names: flow_dir_path, flow_dag_path, flow_path
    flow_dag_path, _ = _load_flow_dag(flow_path)
    flow_dir_path = flow_dag_path.parent
    if _get_additional_includes(flow_dag_path):
        # Merge the flow folder and additional includes to temp folder.
        with _merge_local_code_and_additional_includes(code_path=flow_path) as temp_dir:
            # always overwrite variant since we need to overwrite default variant if not specified.
            overwrite_variant(Path(temp_dir), tuning_node, variant, drop_node_variants=drop_node_variants)
            overwrite_connections(Path(temp_dir), connections)
            remove_additional_includes(Path(temp_dir))
            flow = load_flow(temp_dir)
            yield flow
    else:
        # Generate a flow, the code path points to the original flow folder,
        # the dag path points to the temp dag file after overwriting variant.
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dag_file = Path(temp_dir) / DAG_FILE_NAME
            shutil.copy2(flow_dag_path.resolve().as_posix(), temp_dag_file)
            overwrite_variant(Path(temp_dir), tuning_node, variant, drop_node_variants=drop_node_variants)
            overwrite_connections(Path(temp_dir), connections, working_dir=flow_dir_path)
            flow = Flow(code=flow_dir_path, path=temp_dag_file)
            yield flow


class SubmitterHelper:
    @classmethod
    def init_env(cls, environment_variables):
        # TODO: remove when executor supports env vars in request
        if isinstance(environment_variables, dict):
            os.environ.update(environment_variables)
        elif isinstance(environment_variables, (str, PathLike, Path)):
            load_dotenv(environment_variables)

    @staticmethod
    def resolve_connections(flow: Flow):
        with _change_working_dir(flow.code):
            executable = ExecutableFlow.from_yaml(flow_file=flow.path, working_dir=flow.code)
        executable.name = str(Path(flow.code).stem)

        return get_local_connections_from_executable(executable=executable)

    @classmethod
    def resolve_environment_variables(cls, environment_variables: dict):
        if not environment_variables:
            return None
        connection_names = get_used_connection_names_from_dict(environment_variables)
        connections = cls.resolve_connection_names(connection_names=connection_names)
        update_dict_value_with_connections(built_connections=connections, connection_dict=environment_variables)

    @staticmethod
    def resolve_connection_names(connection_names, raise_error=False):
        from promptflow import PFClient

        local_client = PFClient()
        result = {}
        for n in connection_names:
            try:
                conn = local_client.connections.get(name=n, with_secrets=True)
                result[n] = conn._to_execution_connection_dict()
            except Exception as e:
                if raise_error:
                    raise e
        return result


class RunSubmitter:
    """Submit run to executor."""

    def __init__(self, run_operations: RunOperations):
        self.run_operations = run_operations

    def submit(self, run: Run, stream=False, **kwargs):
        self._run_bulk(run=run, stream=stream, **kwargs)
        return self.run_operations.get(name=run.name)

    def _run_bulk(self, run: Run, stream=False, **kwargs):
        # validate & resolve variant
        if run.variant:
            tuning_node, variant = parse_variant(run.variant)
        else:
            tuning_node, variant = None, None

        if run.run is not None:
            if isinstance(run.run, str):
                run.run = self.run_operations.get(name=run.run)
            elif not isinstance(run.run, Run):
                raise TypeError(f"Referenced run must be a Run instance, got {type(run.run)}")
            else:
                # get the run again to make sure it's status is latest
                run.run = self.run_operations.get(name=run.run.name)
            if run.run.status != Status.Completed.value:
                raise ValueError(f"Referenced run {run.run.name} is not completed, got status {run.run.status}")
            run.run.outputs = self.run_operations._get_outputs(run.run)
        if not run.run and not run.data:
            raise ValueError("Either run or data must be specified for flow run.")

        # running specified variant
        with variant_overwrite_context(run.flow, tuning_node, variant, connections=run.connections) as flow:
            local_storage = LocalStorageOperations(run, stream=stream, run_mode=RunMode.Batch)
            with local_storage.logger:
                self._submit_bulk_run(flow=flow, run=run, local_storage=local_storage)

    def _submit_bulk_run(self, flow: Flow, run: Run, local_storage: LocalStorageOperations) -> dict:
        run_id = run.name
        with _change_working_dir(flow.code):
            connections = SubmitterHelper.resolve_connections(flow=flow)
        column_mapping = run.column_mapping
        # resolve environment variables
        SubmitterHelper.resolve_environment_variables(environment_variables=run.environment_variables)
        SubmitterHelper.init_env(environment_variables=run.environment_variables)

        flow_executor = FlowExecutor.create(
            flow.path,
            connections,
            flow.code,
            storage=local_storage,
        )
        batch_engine = BatchEngine(flow_executor=flow_executor)
        # prepare data
        input_dirs = self._resolve_input_dirs(run)
        self._validate_column_mapping(column_mapping)
        mapped_inputs = batch_engine.get_input_dicts(input_dirs, column_mapping)
        bulk_result = None
        status = Status.Failed.value
        exception = None
        # create run to db when fully prepared to run in executor, otherwise won't create it
        run._dump()  # pylint: disable=protected-access
        try:
            bulk_result = batch_engine.run(
                input_dirs=input_dirs,
                inputs_mapping=column_mapping,
                output_dir=local_storage.outputs_folder,
                run_id=run_id,
            )
            # Filter the failed line result
            failed_line_result = [
                result for result in bulk_result.line_results if result.run_info.status == Status.Failed
            ]
            if failed_line_result:
                # Log warning message when there are failed line run in bulk run.
                error_log = f"{len(failed_line_result)} out of {len(bulk_result.line_results)} runs failed in bulk run."
                if run.properties.get(FlowRunProperties.OUTPUT_PATH, None):
                    error_log = (
                        error_log
                        + f" Please check out {run.properties[FlowRunProperties.OUTPUT_PATH]} for more details."
                    )
                logger.warning(error_log)
            # The bulk run is completed if the exec_bulk successfully completed.
            status = Status.Completed.value
        except Exception as e:
            # when run failed in executor, store the exception in result and dump to file
            logger.warning(f"Run {run.name} failed when executing in executor.")
            exception = e
            # for user error, swallow stack trace and return failed run since user don't need the stack trace
            if not isinstance(e, UserErrorException):
                # for other errors, raise it to user to help debug root cause.
                raise e
            # won't raise the exception since it's already included in run object.
        finally:
            # persist snapshot and result
            # snapshot: flow directory and (mapped) inputs
            local_storage.dump_snapshot(flow)
            local_storage.dump_inputs(mapped_inputs)
            # result: outputs and metrics
            local_storage.persist_result(bulk_result)
            # exceptions
            local_storage.dump_exception(exception=exception, bulk_results=bulk_result)
            # system metrics: token related
            system_metrics = {} if bulk_result is None else bulk_result.get_openai_metrics()

            self.run_operations.update(
                name=run.name,
                status=status,
                end_time=datetime.datetime.now(),
                system_metrics=system_metrics,
            )

    def _resolve_input_dirs(self, run: Run):
        result = {"data": run.data if run.data else None}
        if run.run is not None:
            result.update(
                {
                    "run.outputs": self.run_operations._get_outputs_path(run.run),
                    "run.inputs": self.run_operations._get_inputs_path(run.run),
                }
            )
        return {k: str(Path(v).resolve()) for k, v in result.items() if v is not None}

    @classmethod
    def _validate_column_mapping(cls, column_mapping: dict):
        if not column_mapping:
            return
        if not isinstance(column_mapping, dict):
            raise UserErrorException(f"Column mapping must be a dict, got {type(column_mapping)}.")
        all_static = True
        for v in column_mapping.values():
            if isinstance(v, str) and v.startswith("$"):
                all_static = False
                break
        if all_static:
            raise UserErrorException(
                "Column mapping must contain at least one mapping binding, "
                f"current column mapping contains all static values: {column_mapping}"
            )
