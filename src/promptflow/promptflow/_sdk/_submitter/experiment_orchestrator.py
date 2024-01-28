# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import argparse
import hashlib
import json
import os
import platform
import signal
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

from promptflow._sdk._constants import ExperimentNodeRunStatus, ExperimentNodeType, ExperimentStatus
from promptflow._sdk._errors import (
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
from promptflow._sdk.entities import Run
from promptflow._sdk.entities._experiment import Experiment
from promptflow._utils.logger_utils import LoggerFactory
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
        if platform.system() == "Windows":
            os.spawnv(os.P_DETACH, executable_path, args)
        else:
            os.system(" ".join(["nohup"] + args + ["&"]))
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
                if input_value.startswith("${") and not input_value.startswith("${data."):
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
                    for future, node in future_to_node_run:
                        if future.cancelled():
                            # update status of running nodes to canceled.
                            node.update_exp_run_node(status=ExperimentNodeRunStatus.CANCELED)
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
            self._update_orchestrator_record(status=ExperimentStatus.TERMINATED)
        except Exception as e:
            self._update_orchestrator_record(status=ExperimentStatus.TERMINATED)
            raise RunOperationError(
                message=f"Experiment stopped failed with {e}",
            )
        finally:
            self._update_orchestrator_record(status=ExperimentStatus.TERMINATED)
            if platform.system() == "Windows":
                nodes = ORMExperimentNodeRun.get_node_runs_by_experiment(experiment_name=self.experiment.name)
                for node in nodes or []:
                    if node.status == ExperimentNodeRunStatus.IN_PROGRESS:
                        node.update_status(status=ExperimentNodeRunStatus.CANCELED)

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

        # Use node name as prefix for run name?
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        # Config run output path to experiment output folder
        run_output_path = (Path(experiment._output_dir) / "runs" / node.name).resolve().absolute().as_posix()
        super().__init__(
            name=f"{node.name}_attempt{timestamp}",
            display_name=node.display_name or node.name,
            column_mapping=node.inputs,
            variant=node.variant,
            flow=node.path,
            connections=node.connections,
            environment_variables=node.environment_variables,
            config=Configuration(overrides={Configuration.RUN_OUTPUT_PATH: run_output_path}),
            **kwargs,
        )
        self._resolve_column_mapping()
        self._resolve_data()
        self.snapshot_id = self._calculate_snapshot()

    def _resolve_column_mapping(self):
        """Resolve column mapping with experiment inputs to constant values."""
        logger.info(f"Start resolve node {self.display_name!r} column mapping.")
        resolved_mapping = {}
        for name, value in self.column_mapping.items():
            if not value.startswith("${inputs."):
                resolved_mapping[name] = value
                continue
            input_name = value.split(".")[1].replace("}", "")
            if input_name not in self.experiment_inputs:
                raise ExperimentValueError(
                    f"Node {self.display_name!r} inputs {value!r} related experiment input {input_name!r} not found."
                )
            resolved_mapping[name] = self.experiment_inputs[input_name].default
        logger.debug(f"Resolved node {self.display_name!r} column mapping {resolved_mapping}.")
        self.column_mapping = resolved_mapping

    def _resolve_data(self):
        """Resolve node inputs reference to run or experiment to constant values."""
        logger.info("Start resolve node %s input dirs.", self.name)
        # Get the node referenced data and run
        data_name, run_name = None, None
        data = {}
        for value in self.column_mapping.values():
            referenced_data, referenced_run = None, None
            if value.startswith("${data."):
                referenced_data = value.split(".")[1].replace("}", "")
            elif value.startswith("${"):
                referenced_run = value.split(".")[0].replace("${", "")
            if referenced_data:
                if data_name and data_name != referenced_data:
                    raise ExperimentValueError(
                        f"Experiment has multiple data inputs {data_name!r} and {referenced_data!r}"
                    )
                data_name = referenced_data
            if referenced_run:
                if run_name and run_name != referenced_run:
                    raise ExperimentValueError(
                        f"Experiment has multiple run inputs {run_name!r} and {referenced_run!r}"
                    )
                run_name = referenced_run
            if data_name in self.experiment_data and self.experiment_data[data_name].path:
                data.update({f"data.{data_name}": self.experiment_data[data_name].path})
            if run_name in self.node_runs:
                data.update(
                    {
                        f"{run_name}.outputs": self.run_operations._get_outputs_path(self.node_runs[run_name].name),
                        # to align with cloud behavior, run.inputs should refer to original data
                        f"{run_name}.inputs": self.run_operations._get_data_path(self.node_runs[run_name].name),
                    }
                )
                logger.debug(f"Resolve node {self.name} referenced data {data_name!r}, run {run_name!r}.")
        self._input_data = {k: str(Path(v).resolve()) for k, v in data.items() if v is not None}

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
            "parameter": {},
            "inputs": {key: calculate_files_content_hash(value) for key, value in self._input_data.items()},
            "code": calculate_files_content_hash(self.node.path),
        }
        return hashlib.md5(json.dumps(snapshot_content, sort_keys=True).encode("utf-8")).hexdigest()

    def _run_node(self) -> Run:
        if self.node.type == ExperimentNodeType.FLOW:
            return self._run_flow_node()
        elif self.node.type == ExperimentNodeType.CODE:
            return self._run_script_node()
        elif self.node.type == ExperimentNodeType.CHAT_GROUP:
            return self._run_chat_group_node()
        raise ExperimentValueError(f"Unknown experiment node {self.node.name!r} type {self.node.type!r}")

    def _run_flow_node(self):
        logger.debug(f"Creating run {self.name}")
        exp_node_run_submitter = FlowNodeRunSubmitter(self.run_operations)
        return exp_node_run_submitter.submit(self)

    def _run_script_node(self):
        raise NotImplementedError("Script node in experiment is not supported yet.")

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
        if False and node_run.run_id and node_run.status == ExperimentNodeRunStatus.COMPLETED:
            run_info = ORMRunInfo.get(node_run.run_id)
            run_info_properties = json.loads(run_info.properties)
            output_path = run_info_properties.get("output_path", None)
            if output_path and Path(output_path).exists():
                # TODO Whether need to link used node output folder in the experiment run folder
                logger.info("Reuse exist node run.")
                return run_info
        # Update exp node run record
        self.update_exp_run_node(status=ExperimentNodeRunStatus.IN_PROGRESS)
        node_run_result = self._run_node()
        return node_run_result


class FlowNodeRunSubmitter(RunSubmitter):
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
