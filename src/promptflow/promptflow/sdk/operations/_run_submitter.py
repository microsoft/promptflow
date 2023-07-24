# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# this file is a middle layer between the local SDK and executor, it'll have some similar logic with cloud PFS.
import contextlib
import datetime
import json
import os
import shutil
import tempfile
from os import PathLike
from pathlib import Path

import yaml
from dotenv import load_dotenv

from promptflow.contracts.flow import Flow as ExecutableFlow
from promptflow.contracts.run_mode import RunMode
from promptflow.data import load_data
from promptflow.sdk._constants import (
    DAG_FILE_NAME,
    DEFAULT_VAR_ID,
    NODE,
    NODE_VARIANTS,
    NODES,
    USE_VARIANTS,
    VARIANTS,
    RunTypes,
)
from promptflow.sdk._utils import get_used_connection_names_from_dict, parse_variant, update_dict_value_with_connections
from promptflow.sdk.entities._bulk_flow_run import BulkFlowRun
from promptflow.sdk.entities._flow import Flow
from promptflow.sdk.entities._run import Run
from promptflow.sdk.operations._local_storage_operations import LocalStorageOperations
from promptflow.utils.utils import reverse_transpose

# TODO: move the flow.run flow.bulk_run flow.eval logic to this layer.


def overwrite_variant(flow_path: Path, tuning_node: str, variant: str):
    if flow_path.is_dir():
        flow_path = flow_path / DAG_FILE_NAME
    if not flow_path.exists():
        raise FileNotFoundError(f"Flow file {flow_path} not found")

    with open(flow_path, "r") as f:
        flow_dag = yaml.safe_load(f)

    # check tuning_node & variant
    node_name_2_node = {node["name"]: node for node in flow_dag[NODES]}

    if tuning_node and tuning_node not in node_name_2_node:
        raise ValueError(f"Node {tuning_node} not found in flow")
    if tuning_node and variant:
        try:
            flow_dag[NODE_VARIANTS][tuning_node][VARIANTS][variant]
        except KeyError as e:
            raise ValueError(f"Variant {variant} not found for node {tuning_node}") from e
    try:
        updated_nodes = []
        for node in flow_dag[NODES]:
            if not node.get(USE_VARIANTS, False):
                updated_nodes.append(node)
                continue
            # update variant
            node_name = node["name"]
            variants_cfg = flow_dag[NODE_VARIANTS][node_name]
            variant_id = variant if node_name == tuning_node else None
            if not variant_id:
                variant_id = variants_cfg[DEFAULT_VAR_ID]
            variant_cfg = variants_cfg[VARIANTS][variant_id][NODE]
            updated_nodes.append({"name": node_name, **variant_cfg})
        flow_dag[NODES] = updated_nodes
    except KeyError as e:
        raise KeyError("Failed to overwrite tuning node with variant") from e

    with open(flow_path, "w") as f:
        yaml.safe_dump(flow_dag, f)


@contextlib.contextmanager
def variant_overwrite_context(flow_path: Path, tuning_node: str, variant: str):
    # TODO: store the updated snapshot in flow_snapshot/.runs/run_id/
    with tempfile.TemporaryDirectory() as temp_dir:
        shutil.copytree(flow_path.resolve().as_posix(), temp_dir, dirs_exist_ok=True)
        overwrite_variant(Path(temp_dir), tuning_node, variant)
        flow = Flow.load(temp_dir)
        yield flow


@contextlib.contextmanager
def variant_overwrite_temp_flow(flow_path: Path, tuning_node: str, variant: str):
    """
    Generate a flow, the code path points to the original flow folder,
    the dag path points to the temp dag file after overwriting variant.
    If not provide tuning_node and variant, it will using default variant to overwrite the dag.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dag_file = Path(temp_dir) / DAG_FILE_NAME
        shutil.copy2((flow_path / DAG_FILE_NAME).resolve().as_posix(), temp_dag_file)
        overwrite_variant(Path(temp_dir), tuning_node, variant)
        flow = Flow(code=flow_path, path=temp_dag_file)
        yield flow


class RunSubmitter:
    """Submit run to executor."""

    def __init__(self, run_operations):
        self.run_operations = run_operations

    def submit(self, run: Run, stream=False, **kwargs):
        run._dump()  # pylint: disable=protected-access
        raw_run = self._run_bulk(run=run, stream=stream, **kwargs)
        self.run_operations.update(
            name=run.name,
            status=raw_run["flow_runs"][0]["status"],
            end_time=datetime.datetime.now(),
        )
        return self.run_operations.get(name=run.name)

    @classmethod
    def _dump_outputs(cls, run: Run, raw_run: BulkFlowRun) -> None:
        # TODO: the data should be returned directly from the executor.
        run._output_path.mkdir(parents=True, exist_ok=True)
        # remove inputs lines as it overlaps with new `_dump_snapshot`
        # output
        if raw_run.output:
            with open(run._output_path / "output.json", "w") as f:
                json.dump(raw_run.output, f, indent=4)
        # detail
        with open(run._output_path / "detail.json", "w") as f:
            json.dump(raw_run.detail, f, indent=4)
        # remove metrics lines as it overlaps with new `_dump_executor_result`

    @classmethod
    def _dump_executor_result(cls, local_storage, flow: Flow, executor_result: dict) -> None:
        """Dump executor return to local storage."""
        local_storage.dump_outputs(outputs=executor_result["flow_runs"][0]["output"])
        local_storage.dump_metrics(metrics=executor_result["flow_runs"][0].get("metrics", None))
        local_storage.dump_details(details=executor_result)
        # local storage related: snapshot, outputs and metrics
        local_storage.dump_snapshot(flow=flow)
        # for batch run, directly dump; otherwise, extra record line number
        if local_storage._run.type == RunTypes.EVALUATION:
            local_storage.dump_eval_inputs_from_legacy_executor_result(executor_result)
        else:
            local_storage.dump_inputs(inputs=executor_result["inputs"])

    def _run_bulk(self, run: Run, stream=False, **kwargs):
        # validate & resolve variant
        if run.variant:
            tuning_node, variant = parse_variant(run.variant)
        else:
            tuning_node, variant = None, None

        if run.run is not None:
            if isinstance(run.run, str):
                run.run = self.run_operations.get(name=run.run)
            if not isinstance(run.run, Run):
                raise TypeError(f"run must be a Run instance, got {run.run}")
            run.run.outputs = self.run_operations.get_outputs(run.run)
        if not run.run and not run.data:
            raise ValueError("Either run or data must be specified for flow run.")

        # running specified variant
        with variant_overwrite_context(run.flow, tuning_node, variant) as flow:
            local_storage = LocalStorageOperations(run)
            with local_storage.setup_logger(stream=stream):
                raw_run = self._submit_bulk_run(flow=flow, run=run)
            # BulkFlowRun.detail is actually return of executor
            self._dump_executor_result(local_storage=local_storage, flow=flow, executor_result=raw_run)

        return raw_run

    def _submit_bulk_run(self, flow: Flow, run: Run):
        # TODO(2526443): use executor's new API to submit
        flow_id = run.flow.as_posix()
        run_id = run.name
        connections = self._resolve_connections(flow=flow)
        inputs_mapping = run.column_mapping
        # resolve environment variables
        self._resolve_environment_variables(run=run)
        coodinator = self._init_coordinator_from_env(run.environment_variables)

        run_tracker = coodinator._run_tracker
        run_tracker._run_mode = RunMode.BulkTest
        run_tracker._activate_in_context()
        root_run_info = run_tracker.start_root_flow_run(
            flow_id=flow_id, root_run_id=run_id, run_id=run_id, parent_run_id=""
        )
        mapped_inputs = None
        try:
            # prepare data
            input_dicts = self._resolve_data(run)

            flow_executor = coodinator.create_flow_executor_by_yaml(flow.path, connections, flow.code)
            flow_executor._run_tracker._activate_in_context()
            mapped_inputs = flow_executor.apply_inputs_mapping_for_all_lines(input_dicts, inputs_mapping)
            bulk_result = flow_executor.exec_batch(mapped_inputs, root_run_info)

            flow_executor._run_tracker._deactivate_in_context()
            run_tracker.end_run(run_id, result=bulk_result, update_at_last=True)
        except Exception as e:
            run_tracker.end_run(run_id, ex=e, update_at_last=True)
        finally:
            run_tracker._deactivate_in_context()
            # Todo: end bulk test
        result = run_tracker.collect_all_run_infos_as_dicts()
        # TODO: get the inputs from executor result
        result["inputs"] = mapped_inputs
        return result

    @classmethod
    def _init_coordinator_from_env(cls, environment_variables):
        from promptflow.executor.executor import FlowExecutionCoodinator

        # TODO: remove when executor supports env vars in request
        if isinstance(environment_variables, dict):
            os.environ.update(environment_variables)
        elif isinstance(environment_variables, (str, PathLike, Path)):
            load_dotenv(environment_variables)

        return FlowExecutionCoodinator.init_from_env()

    @classmethod
    def _resolve_connections(cls, flow: Flow):
        executable = ExecutableFlow.from_yaml(flow_file=flow.path, working_dir=flow.code)

        return Flow._get_local_connections(executable=executable)

    def _resolve_data(self, run: Run):
        result = {}
        input_dicts = {}
        if run.data:
            input_dicts["data"] = run.data
        for input_key, local_file in input_dicts.items():
            result[input_key] = load_data(local_file)
        if run.run is not None:
            variant_output = reverse_transpose(self.run_operations.get_outputs(run.run))
            result["run.outputs"] = variant_output
            variant_input = reverse_transpose(self.run_operations.get_inputs(run.run))
            result["run.inputs"] = variant_input
        return result

    def _resolve_connection_names(self, connection_names, raise_error=False):
        from promptflow import PFClient

        local_client = PFClient()
        result = {}
        for n in connection_names:
            try:
                conn = local_client.connections.get(name=n, with_secrets=True)
                result[n] = conn.to_execution_connection_dict()
            except Exception as e:
                if raise_error:
                    raise e
        return result

    def _resolve_environment_variables(self, run: Run):
        if not run.environment_variables:
            return None
        connection_names = get_used_connection_names_from_dict(run.environment_variables)
        connections = self._resolve_connection_names(connection_names=connection_names)
        update_dict_value_with_connections(built_connections=connections, connection_dict=run.environment_variables)
