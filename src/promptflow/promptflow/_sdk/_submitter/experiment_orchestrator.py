# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import argparse
import hashlib
import json
import os
import platform
import signal
import subprocess
import sys
from concurrent import futures
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from os import PathLike
from pathlib import Path

import psutil

if not sys.stdout:
    sys.stdout = open(os.devnull, "w")
if not sys.stderr:
    sys.stderr = sys.stdout

from promptflow._sdk._constants import ExperimentNodeRunStatus, ExperimentNodeType, ExperimentStatus, FlowRunProperties
from promptflow._sdk._errors import (
    ExperimentCommandRunError,
    ExperimentNodeRunFailedError,
    ExperimentNotFoundError,
    ExperimentValueError,
    RunOperationError,
)
from promptflow._sdk._orm.experiment import Experiment as ORMExperiment
from promptflow._sdk._orm.experiment_node_run import ExperimentNodeRun as ORMExperimentNodeRun
from promptflow._sdk._orm.orchestrator import Orchestrator as ORMOrchestrator
from promptflow._sdk._orm.run_info import RunInfo as ORMRunInfo
from promptflow._sdk._submitter import RunSubmitter
from promptflow._sdk._submitter.utils import SubmitterHelper
from promptflow._sdk.entities import Run
from promptflow._sdk.entities._experiment import Experiment
from promptflow._sdk.operations import RunOperations
from promptflow._sdk.operations._local_storage_operations import LocalStorageOperations
from promptflow._utils.logger_utils import LoggerFactory
from promptflow.contracts.run_info import Status
from promptflow.contracts.run_mode import RunMode
from promptflow.exceptions import ErrorTarget, UserErrorException

logger = LoggerFactory.get_logger(name=__name__)
SNAPSHOT_IGNORES = ["__pycache__"]


class ExperimentOrchestrator:
    """Experiment orchestrator, responsible for experiment running and status checking."""

    def __init__(self, run_operations, experiment_operations, experiment: Experiment):
        self.run_operations = run_operations
        self.experiment_operations = experiment_operations
        self.experiment = experiment
        self._nodes = {node.name: node for node in self.experiment.nodes}
        # A key-value pair of node name and run info
        self._node_runs = {}

    def start(self, nodes=None, from_nodes=None):
        """Start an experiment.

        :param nodes: Nodes to be executed.
        :type nodes: list
        :param from_nodes: The branches in experiment to be executed.
        :type from_nodes: list
        :return: Experiment info.
        :rtype: ~promptflow.entities.Experiment
        """
        # Update experiment status
        logger.info(f"Start experiment {self.experiment.name}.")
        self._update_orchestrator_record(status=ExperimentStatus.IN_PROGRESS, pid=os.getpid())
        self._start_orchestrator(nodes=nodes, from_nodes=from_nodes)
        # Return experiment info
        return self.experiment

    def async_start(self, executable_path=None, nodes=None, from_node=None):
        """Start an experiment async.

        :param executable_path: Python path when executing the experiment.
        :type executable_path: str
        :param nodes: Nodes to be executed.
        :type nodes: list
        :param from_nodes: The branches in experiment to be executed.
        :type from_nodes: list
        :return: Experiment info.
        :rtype: ~promptflow.entities.Experiment
        """
        logger.info(f"Queuing experiment {self.experiment.name}.")
        self._update_orchestrator_record(status=ExperimentStatus.QUEUING)

        executable_path = executable_path or sys.executable
        args = [executable_path, __file__, "start", "--experiment", self.experiment.name]
        if nodes:
            args = args + ["--nodes"] + nodes
        if from_node:
            args = args + ["--from-nodes"] + from_node
        # Start an orchestrator process using detach mode
        logger.debug(f"Start experiment {self.experiment.name} in background.")
        if platform.system() == "Windows":
            os.spawnve(os.P_DETACH, executable_path, args, os.environ)
        else:
            subprocess.Popen(" ".join(["nohup"] + args + ["&"]), shell=True, env=os.environ)
            print(" ".join(["nohup"] + args + ["&"]))
        return self.experiment

    def _update_orchestrator_record(self, status, pid=None):
        """Update orchestrator table data"""
        orm_orchestrator = ORMOrchestrator(
            experiment_name=self.experiment.name,
            pid=pid,
            status=status,
        )
        ORMOrchestrator.create_or_update(orm_orchestrator)

        self.experiment.status = status
        last_start_time, last_end_time = None, None
        if status == ExperimentStatus.IN_PROGRESS:
            last_start_time = datetime.utcnow().isoformat()
        elif status == ExperimentStatus.TERMINATED:
            last_end_time = datetime.utcnow().isoformat()
        return ORMExperiment.get(name=self.experiment.name).update(
            status=self.experiment.status,
            last_start_time=last_start_time,
            last_end_time=last_end_time,
            node_runs=json.dumps(self.experiment.node_runs),
        )

    def _start_orchestrator(self, nodes=None, from_nodes=None):
        """
        Orchestrate the execution of nodes in the experiment.
        Determine node execution order through topological sorting.

        :param nodes: Nodes to be executed.
        :type nodes: list
        :param from_nodes: The branches in experiment to be executed.
        :type from_nodes: list
        """

        def prepare_edges(node):
            """Get all in-degree nodes of this node."""
            node_names = set()
            for input_value in node.inputs.values():
                if not isinstance(input_value, str):
                    continue
                if (
                    input_value.startswith("${")
                    and not input_value.startswith("${data.")
                    and not input_value.startswith("${inputs.")
                ):
                    referenced_node_name = input_value.split(".")[0].replace("${", "")
                    node_names.add(referenced_node_name)
            return node_names

        def get_next_executable_nodes(completed_node=None):
            """Get the node to be executed in the experiment.

            :param completed_node: The completed node is used to update node-edge mapping in experiment run.
            :type completed_node: str
            :param next_executable_nodes: Executable node list.
            :type next_executable_nodes: list
            """
            if completed_node:
                # Update node edge mapping in current experiment run.
                # Remove the edge of the node that has been completed.
                for referenced_nodes in node_edges_mapping.values():
                    referenced_nodes.discard(completed_node)
            next_executable_nodes = [
                self._nodes[node_name] for node_name, edges in node_edges_mapping.items() if len(edges) == 0
            ]
            for node in next_executable_nodes:
                node_edges_mapping.pop(node.name)
            return next_executable_nodes

        def check_in_degree_node_outputs(node, node_edges_mapping):
            in_degree_nodes = []
            for in_degree_node, edges in node_edges_mapping.items():
                if node in edges:
                    in_degree_nodes.append(in_degree_node)
            node_runs = {
                node.name: node
                for node in ORMExperimentNodeRun.get_node_runs_by_experiment(experiment_name=self.experiment.name)
                if node.status == ExperimentNodeRunStatus.COMPLETED
            }
            is_in_degree_nodes_ready = True
            for in_degree_node in in_degree_nodes:
                is_in_degree_nodes_ready = in_degree_node in node_runs
                if in_degree_node in node_runs:
                    node_run_info = node_runs[in_degree_node]
                    run_info_properties = json.loads(node_run_info.properties)
                    output_path = run_info_properties.get("output_path", None)
                    is_in_degree_nodes_ready = is_in_degree_nodes_ready and Path(output_path).exists()
            return is_in_degree_nodes_ready

        if platform.system() != "Windows":

            def stop_handler(signum, frame):
                """
                Post-processing when the experiment is canceled.
                Terminate all executing nodes and update node status.
                """
                if signum == signal.SIGTERM:
                    self._update_orchestrator_record(status=ExperimentStatus.TERMINATED)
                    executor.shutdown(wait=False)
                    for future, node in future_to_node_run.items():
                        if future.cancelled():
                            # update status of running nodes to canceled.
                            node.update_exp_run_node(status=ExperimentNodeRunStatus.CANCELED)
                            self.experiment.node_runs[node.name] = ORMExperimentNodeRun.get(node.run_id)
                    sys.exit(1)

            signal.signal(signal.SIGTERM, stop_handler)

        # TODO set max workers
        executor = ThreadPoolExecutor(max_workers=None)
        future_to_node_run = {}

        node_edges_mapping = {node.name: prepare_edges(node) for node in self.experiment.nodes}
        logger.debug(f"Experiment nodes edges: {node_edges_mapping!r}")

        if from_nodes:
            # Executed from specified nodes
            # check in-degree nodes outputs exist
            for node in from_nodes:
                if not check_in_degree_node_outputs(node, node_edges_mapping):
                    raise UserErrorException(f"The output of in-degree of node {node} does not exist.")
            next_execute_nodes = from_nodes
        elif nodes:
            # Executed specified nodes
            # check in-degree nodes outputs exist
            for node in nodes:
                if not check_in_degree_node_outputs(node, node_edges_mapping):
                    raise UserErrorException(f"The output of in-degree of node {node} does not exist.")
            next_execute_nodes = nodes
        else:
            # Execute all nodes in experiment.
            next_execute_nodes = get_next_executable_nodes()

        while len(next_execute_nodes) != 0 or len(future_to_node_run) != 0:
            for node in next_execute_nodes:
                # Start node execution.
                logger.info(f"Running node {node.name}.")
                exp_node_run = ExperimentNodeRun(
                    node=node,
                    experiment=self.experiment,
                    node_runs=self._node_runs,
                    run_operations=self.run_operations,
                )
                future_to_node_run[executor.submit(exp_node_run.submit)] = exp_node_run
            completed_futures, _ = futures.wait(future_to_node_run.keys(), return_when=futures.FIRST_COMPLETED)
            next_execute_nodes = []
            for future in completed_futures:
                try:
                    node_name = future_to_node_run[future].node.name
                    self._node_runs[node_name] = future.result()
                    if not nodes:
                        next_execute_nodes.extend(get_next_executable_nodes(completed_node=node_name))
                    self.experiment._append_node_run(node_name, self._node_runs[node_name])
                    del future_to_node_run[future]
                except Exception as e:
                    executor.shutdown(wait=False)
                    # Handle failed execution, update orchestrator and experiment info
                    self.experiment._append_node_run(node_name, future_to_node_run[future])
                    self._update_orchestrator_record(status=ExperimentStatus.TERMINATED)
                    logger.warning(f"Node {future_to_node_run[future].node.name} failed to execute with error {e}.")
                    raise ExperimentNodeRunFailedError(
                        f"Node {future_to_node_run[future].node.name} failed to execute with error {e}."
                    )
        executor.shutdown(wait=False)
        self._update_orchestrator_record(status=ExperimentStatus.TERMINATED)

    def stop(self):
        orchestrator = ORMOrchestrator.get(experiment_name=self.experiment.name)
        if orchestrator.status in [ExperimentStatus.NOT_STARTED, ExperimentStatus.QUEUING, ExperimentStatus.TERMINATED]:
            raise UserErrorException(
                target=ErrorTarget.CONTROL_PLANE_SDK,
                message="Experiment cannot be stopped if it is not started.",
            )
        try:
            process = psutil.Process(orchestrator.pid)
            process.terminate()
        except psutil.NoSuchProcess:
            logger.debug("Experiment orchestrator process terminates abnormally.")
        except Exception as e:
            raise RunOperationError(
                message=f"Experiment stopped failed with {e}",
            )
        finally:
            if platform.system() == "Windows":
                nodes = ORMExperimentNodeRun.get_node_runs_by_experiment(experiment_name=self.experiment.name)
                for node in nodes or []:
                    if node.status == ExperimentNodeRunStatus.IN_PROGRESS:
                        node.update_status(status=ExperimentNodeRunStatus.CANCELED)
                        self.experiment.node_runs[node.name] = ORMExperimentNodeRun.get(run_id=node.run_id)
                    else:
                        self.experiment.node_runs[node.name] = node
            self._update_orchestrator_record(status=ExperimentStatus.TERMINATED)

    @staticmethod
    def get_status(experiment_name):
        def set_orchestrator_terminated():
            logger.info(
                "The orchestrator process terminates abnormally, "
                f"status of {experiment_name} is updated to terminated."
            )
            orm_orchestrator.status = ExperimentStatus.TERMINATED
            ORMOrchestrator.create_or_update(orm_orchestrator)
            ORMExperiment.get(name=experiment_name).update(status=ExperimentStatus.TERMINATED)

        try:
            orm_orchestrator = ORMOrchestrator.get(experiment_name=experiment_name)
            if orm_orchestrator.status == ExperimentStatus.IN_PROGRESS:
                try:
                    process = psutil.Process(orm_orchestrator.pid)
                    if experiment_name not in process.cmdline():
                        set_orchestrator_terminated()
                    return orm_orchestrator.status
                except psutil.NoSuchProcess:
                    set_orchestrator_terminated()
                    return ExperimentStatus.TERMINATED
            else:
                return orm_orchestrator.status
        except ExperimentNotFoundError:
            return ExperimentStatus.NOT_STARTED


class ExperimentNodeRun(Run):
    """Experiment node run, includes experiment running context, like data, inputs and runs."""

    def __init__(self, node, experiment, node_runs, run_operations, **kwargs):
        from promptflow._sdk._configuration import Configuration

        self.node = node
        self.experiment = experiment
        self.experiment_data = {data.name: data for data in experiment.data}
        self.experiment_inputs = {input.name: input for input in experiment.inputs}
        self.node_runs = node_runs
        self.run_operations = run_operations

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        # Config run output path to experiment output folder
        run_output_path = (Path(experiment._output_dir) / "runs" / node.name).resolve().absolute().as_posix()
        super().__init__(
            # Use node name as prefix for run name?
            name=f"{node.name}_attempt{timestamp}",
            display_name=node.display_name or node.name,
            column_mapping=node.inputs,
            variant=getattr(node, "variant", None),
            flow=self._get_node_path(),
            outputs=getattr(node, "outputs", None),
            connections=getattr(node, "connections", None),
            command=getattr(node, "command", None),
            environment_variables=node.environment_variables,
            config=Configuration(overrides={Configuration.RUN_OUTPUT_PATH: run_output_path}),
            **kwargs,
        )
        self._resolve_column_mapping()
        self._input_data = self._resolve_input_dirs()
        self.snapshot_id = self._calculate_snapshot()

    def _resolve_column_mapping(self):
        """Resolve column mapping with experiment inputs to constant values."""
        logger.info(f"Start resolve node {self.node.name!r} column mapping.")
        resolved_mapping = {}
        for name, value in self.column_mapping.items():
            if not isinstance(value, str) or not value.startswith("${inputs."):
                resolved_mapping[name] = value
                continue
            input_name = value.split(".")[1].replace("}", "")
            if input_name not in self.experiment_inputs:
                raise ExperimentValueError(
                    f"Node {self.node_name!r} inputs {value!r} related experiment input {input_name!r} not found."
                )
            resolved_mapping[name] = self.experiment_inputs[input_name].default
        logger.debug(f"Resolved node {self.node.name!r} column mapping {resolved_mapping}.")
        self.column_mapping = resolved_mapping

    def _get_referenced_data_and_run(self) -> tuple:
        """Get the node referenced data and runs. Format: {name: ExperimentData/ExperimentRun}"""
        data, run = {}, {}
        inputs_mapping = self.column_mapping
        for value in inputs_mapping.values():
            if not isinstance(value, str):
                continue
            if value.startswith("${data."):
                name = value.split(".")[1].replace("}", "")
                if name not in self.experiment_data:
                    raise ExperimentValueError(
                        f"Node {self.display_name!r} inputs {value!r} related experiment data {name!r} not found."
                    )
                data[name] = self.experiment_data[name]
            elif value.startswith("${"):
                name = value.split(".")[0].replace("${", "")
                if name not in self.node_runs:
                    raise ExperimentValueError(
                        f"Node {self.display_name!r} inputs {value!r} related experiment run {name!r} not found."
                    )
                run[name] = self.node_runs[name]
        return data, run

    @staticmethod
    def resolve_binding_from_run(run_name, run, run_operations) -> dict:
        """Return the valid binding dict based on a run."""
        binding_dict = {
            # to align with cloud behavior, run.inputs should refer to original data
            f"{run_name}.inputs": run_operations._get_data_path(run),
        }

        # Update command node outputs
        if run._outputs:
            binding_dict.update({f"{run_name}.outputs.{name}": path for name, path in run._outputs.items()})
        else:
            binding_dict.update({f"{run_name}.outputs": run_operations._get_outputs_path(run)})
        logger.debug(f"Resolved node {run_name} binding inputs {binding_dict}.")
        return binding_dict

    def _resolve_input_dirs(self):
        logger.info("Start resolve node %s input dirs.", self.node.name)
        # Get the node referenced data and run
        referenced_data, referenced_run = self._get_referenced_data_and_run()
        if len(referenced_data) > 1:
            raise ExperimentValueError(
                f"Experiment flow node {self.node.name!r} has multiple data inputs {referenced_data}, "
                "only 1 is expected."
            )
        if len(referenced_run) > 1:
            raise ExperimentValueError(
                f"Experiment flow node {self.node.name!r} has multiple run inputs {referenced_run}, "
                "only 1 is expected."
            )
        (data_name, data_obj) = next(iter(referenced_data.items())) if referenced_data else (None, None)
        (run_name, run_obj) = next(iter(referenced_run.items())) if referenced_run else (None, None)
        logger.debug(f"Resolve node {self.node.name} referenced data {data_name!r}, run {run_name!r}.")
        # Build inputs from experiment data and run
        result = {}
        if data_obj:
            result.update({f"data.{data_name}": data_obj.path})
        if run_obj:
            result.update(self.resolve_binding_from_run(run_name, run_obj, self.run_operations))
        result = {k: str(Path(v).resolve()) for k, v in result.items() if v is not None}
        logger.debug(f"Resolved node {self.node.name} input dirs {result}.")
        return result

    def _calculate_snapshot(self):
        def calculate_files_content_hash(file_path):
            file_content = {}
            if not isinstance(file_path, (str, PathLike)) or not Path(file_path).exists():
                return file_path
            if Path(file_path).is_file():
                with open(file_path, "r") as f:
                    file_content[file_path] = hashlib.md5(f.read().encode("utf8")).hexdigest()
            else:
                for root, dirs, files in os.walk(file_path):
                    for ignore_item in SNAPSHOT_IGNORES:
                        if ignore_item in dirs:
                            dirs.remove(ignore_item)
                    for file in files:
                        with open(os.path.join(root, file), "r") as f:
                            relative_path = (Path(root) / file).relative_to(Path(file_path)).as_posix()
                            try:
                                file_content[relative_path] = hashlib.md5(f.read().encode("utf8")).hexdigest()
                            except Exception as e:
                                raise e
            return hashlib.md5(json.dumps(file_content, sort_keys=True).encode("utf-8")).hexdigest()

        snapshot_content = {
            "column_mapping": self.column_mapping,
            "inputs": {key: calculate_files_content_hash(value) for key, value in self._input_data.items()},
            "code": calculate_files_content_hash(self.flow),
        }
        return hashlib.md5(json.dumps(snapshot_content, sort_keys=True).encode("utf-8")).hexdigest()

    def _get_node_path(self):
        if self.node.type == ExperimentNodeType.FLOW:
            return self.node.path
        elif self.node.type == ExperimentNodeType.COMMAND:
            return self.node.code
        elif self.node.type == ExperimentNodeType.CHAT_GROUP:
            raise NotImplementedError("Chat group node in experiment is not supported yet.")
        raise ExperimentValueError(f"Unknown experiment node {self.node.name!r} type {self.node.type!r}")

    def _run_node(self) -> Run:
        if self.node.type == ExperimentNodeType.FLOW:
            return self._run_flow_node()
        elif self.node.type == ExperimentNodeType.COMMAND:
            return self._run_command_node()
        elif self.node.type == ExperimentNodeType.CHAT_GROUP:
            return self._run_chat_group_node()
        raise ExperimentValueError(f"Unknown experiment node {self.node.name!r} type {self.node.type!r}")

    def _run_flow_node(self):
        logger.debug(f"Creating flow run {self.name}")
        exp_node_run_submitter = ExperimentFlowRunSubmitter(self.run_operations)
        return exp_node_run_submitter.submit(self)

    def _run_command_node(self):
        logger.debug(f"Creating command run {self.name}")
        exp_command_submitter = ExperimentCommandSubmitter(self.run_operations)
        return exp_command_submitter.submit(self)

    def _run_chat_group_node(self):
        raise NotImplementedError("Chat group node in experiment is not supported yet.")

    def update_exp_run_node(self, status):
        node_run = ORMExperimentNodeRun(
            run_id=self.name,
            snapshot_id=self.snapshot_id,
            node_name=self.node.name,
            experiment_name=self.experiment.name,
            status=status,
        )
        ORMExperimentNodeRun.create_or_update(node_run)

    def submit(self):
        # Get snapshot id from exp_node_run
        node_run = ORMExperimentNodeRun.get_completed_node_by_snapshot_id(
            snapshot_id=self.snapshot_id, experiment_name=self.experiment.name, raise_error=False
        )
        if node_run and node_run.run_id and node_run.status == ExperimentNodeRunStatus.COMPLETED:
            run_info = ORMRunInfo.get(node_run.run_id)
            run_info_properties = json.loads(run_info.properties)
            output_path = run_info_properties.get("output_path", None)
            if output_path and Path(output_path).exists():
                # TODO Whether need to link used node output folder in the experiment run folder
                logger.info(f"Reuse exist node run {run_info.name} for node {self.node.name}.")
                return run_info
        # Update exp node run record
        self.update_exp_run_node(status=ExperimentNodeRunStatus.IN_PROGRESS)
        node_run_result = self._run_node()
        logger.info(f"Node {self.node.name} run {self.name} completed, outputs to {node_run_result._output_path}.")
        return node_run_result


class ExperimentFlowRunSubmitter(RunSubmitter):
    """Experiment run submitter, override some function from RunSubmitter as experiment run could be different."""

    @classmethod
    def _validate_inputs(cls, run: Run):
        # Do not validate run/data field, as we will resolve them in _resolve_input_dirs.
        return

    def _resolve_input_dirs(self, run: ExperimentNodeRun):
        return run._input_data

    def submit(self, run: Run, stream=False, **kwargs):
        try:
            run.update_exp_run_node(ExperimentNodeRunStatus.IN_PROGRESS)
            self._run_bulk(run=run, stream=stream, **kwargs)
            run_info = self.run_operations.get(name=run.name)
            run.update_exp_run_node(run_info.status)
            return run_info
        except Exception as e:
            run.update_exp_run_node(ExperimentNodeRunStatus.FAILED)
            raise e


class ExperimentCommandSubmitter:
    """Experiment command submitter, responsible for experiment command running."""

    def __init__(self, run_operations: RunOperations):
        self.run_operations = run_operations

    def submit(self, run: ExperimentNodeRun, **kwargs):
        """Submit an experiment command run.

        :param run: Experiment command to submit.
        :type run: ~promptflow.entities.Run
        """
        local_storage = LocalStorageOperations(run, run_mode=RunMode.SingleNode)
        self._submit_command_run(run=run, local_storage=local_storage)
        return self.run_operations.get(name=run.name)

    def _resolve_inputs(self, run: ExperimentNodeRun):
        """Resolve binding inputs to constant values."""
        # e.g. "input_path": "${data.my_data}" -> "${inputs.input_path}": "real_data_path"
        logger.info("Start resolve node %s inputs.", run.node.name)

        logger.debug(f"Resolved node {run.node.name} binding inputs {run._input_data}.")
        # resolve inputs
        resolved_inputs = {}
        for name, value in run.column_mapping.items():
            if not isinstance(value, str) or not value.startswith("${"):
                resolved_inputs[name] = value
                continue
            # my_input: "${run.outputs}" -> my_input: run_outputs_path
            input_key = value.lstrip("${").rstrip("}")
            if input_key in run._input_data:
                resolved_inputs[name] = run._input_data[input_key]
                continue
            logger.warning(
                f"Possibly invalid partial input value binding {value!r} found for node {run.node.name!r}. "
                "Only full binding is supported for command node. For example: ${data.my_data}, ${main_node.outputs}."
            )
            resolved_inputs[name] = value
        logger.debug(f"Resolved node {run.node.name} inputs {resolved_inputs}.")
        return resolved_inputs

    def _resolve_outputs(self, run: ExperimentNodeRun):
        """Resolve outputs to real path."""
        # e.g. "output_path": "${outputs.my_output}" -> "${outputs.output_path}": "real_output_path"
        logger.info("Start resolve node %s outputs.", run.node.name)
        # resolve outputs
        resolved_outputs = {}
        for name, value in run._outputs.items():
            # Set default output path if user doesn't set it
            if not value:
                # Create default output path if user doesn't set it
                value = run._output_path / name
                value.mkdir(parents=True, exist_ok=True)
                value = value.resolve().absolute().as_posix()
                # Update default to run
                run._outputs[name] = value
            # Note: We will do nothing if user config the value, as we don't know it's a file or folder
            resolved_outputs[name] = value
        logger.debug(f"Resolved node {run.node.name} outputs {resolved_outputs}.")
        return resolved_outputs

    def _resolve_command(self, run: ExperimentNodeRun, inputs: dict, outputs: dict):
        """Resolve command to real command."""
        logger.info("Start resolve node %s command.", run.node.name)
        # resolve command
        resolved_command = run._command
        # replace inputs
        for name, value in inputs.items():
            resolved_command = resolved_command.replace(f"${{inputs.{name}}}", str(value))
        # replace outputs
        for name, value in outputs.items():
            resolved_command = resolved_command.replace(f"${{outputs.{name}}}", str(value))
        logger.debug(f"Resolved node {run.node.name} command {resolved_command}.")
        if "${" in resolved_command:
            logger.warning(
                f"Possibly unresolved command value binding found for node {run.node.name!r}. "
                f"Resolved command: {resolved_command}. Please check your command again."
            )
        return resolved_command

    def _submit_command_run(self, run: ExperimentNodeRun, local_storage: LocalStorageOperations) -> dict:
        # resolve environment variables
        SubmitterHelper.resolve_environment_variables(environment_variables=run.environment_variables)
        SubmitterHelper.init_env(environment_variables=run.environment_variables)

        # resolve inputs & outputs for command preparing
        # e.g. input_path: ${data.my_data} -> ${inputs.input_path}: real_data_path
        inputs = self._resolve_inputs(run)
        outputs = self._resolve_outputs(run)

        # replace to command
        command = self._resolve_command(run, inputs, outputs)

        # execute command
        status = Status.Failed.value
        # create run to db when fully prepared to run in executor, otherwise won't create it
        run._dump()  # pylint: disable=protected-access
        try:
            return_code = ExperimentCommandExecutor.run(command=command, cwd=run.flow, local_storage=local_storage)
            if return_code != 0:
                raise ExperimentCommandRunError(
                    f"Run {run.name} failed with return code {return_code}, "
                    f"please check out {run.properties[FlowRunProperties.OUTPUT_PATH]} for more details."
                )
            status = Status.Completed.value
        except Exception as e:
            # when run failed in executor, store the exception in result and dump to file
            logger.warning(f"Run {run.name} failed when executing in executor with exception {e}.")
            # for user error, swallow stack trace and return failed run since user don't need the stack trace
            if not isinstance(e, UserErrorException):
                # for other errors, raise it to user to help debug root cause.
                raise e
        finally:
            self.run_operations.update(
                name=run.name,
                status=status,
                end_time=datetime.now(),
            )


class ExperimentCommandExecutor:
    """Experiment command executor, responsible for experiment command running."""

    @staticmethod
    def run(command: str, cwd: str, local_storage: LocalStorageOperations):
        """Start a subprocess to run the command"""
        log_path = local_storage.logger.file_path
        logger.info(f"Start running command {command}, log path: {log_path}.")
        with open(log_path, "w") as log_file:
            process = subprocess.Popen(command, stdout=log_file, stderr=log_file, shell=True, env=os.environ, cwd=cwd)
        process.wait()
        return process.returncode


def add_start_orchestrator_action(subparsers):
    """Add action to start orchestrator."""
    start_orchestrator_parser = subparsers.add_parser(
        "start",
        description="Start orchestrator.",
    )
    start_orchestrator_parser.add_argument("--experiment", type=str, help="Experiment name")
    start_orchestrator_parser.add_argument("--nodes", type=str, help="Nodes to be executed", nargs="+")
    start_orchestrator_parser.add_argument("--from-nodes", type=str, help="Nodes branch to be executed", nargs="+")
    start_orchestrator_parser.set_defaults(action="start")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Orchestrator operations",
    )
    subparsers = parser.add_subparsers()
    add_start_orchestrator_action(subparsers)

    args = args = parser.parse_args(sys.argv[1:])

    if args.action == "start":
        from promptflow._sdk._pf_client import PFClient

        client = PFClient()
        experiment = client._experiments.get(args.experiment)
        ExperimentOrchestrator(
            run_operations=client.runs, experiment_operations=client._experiments, experiment=experiment
        ).start(nodes=args.nodes, from_nodes=args.from_nodes)
