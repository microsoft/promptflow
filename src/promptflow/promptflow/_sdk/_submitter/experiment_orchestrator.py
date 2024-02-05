# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import argparse
import copy
import json
import os
import platform
import signal
import subprocess
import sys
import tempfile
import uuid
from concurrent import futures
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Union

import psutil

# For the process started in detach mode, stdout/std error will be none.
# To avoid exception to stdout/stderr calls in the dependency package, point stdout/stderr to devnull.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = sys.stdout

from promptflow._sdk._constants import (
    PF_TRACE_CONTEXT,
    PROMPT_FLOW_DIR_NAME,
    ExperimentContextKey,
    ExperimentNodeRunStatus,
    ExperimentNodeType,
    ExperimentStatus,
    FlowRunProperties,
)
from promptflow._sdk._errors import (
    ExperimentCommandRunError,
    ExperimentHasCycle,
    ExperimentNodeRunFailedError,
    ExperimentNotFoundError,
    ExperimentValueError,
)
from promptflow._sdk._orm.experiment import Experiment as ORMExperiment
from promptflow._sdk._orm.experiment_node_run import ExperimentNodeRun as ORMExperimentNodeRun
from promptflow._sdk._orm.orchestrator import Orchestrator as ORMOrchestrator
from promptflow._sdk._orm.run_info import RunInfo as ORMRunInfo
from promptflow._sdk._submitter import RunSubmitter
from promptflow._sdk._submitter.utils import (
    SubmitterHelper,
    _calculate_snapshot,
    _start_process_in_background,
    _stop_orchestrator_process,
    _windows_stop_handler,
)
from promptflow._sdk.entities import Run
from promptflow._sdk.entities._experiment import Experiment, ExperimentTemplate
from promptflow._sdk.entities._flow import ProtectedFlow
from promptflow._sdk.operations import RunOperations
from promptflow._sdk.operations._local_storage_operations import LocalStorageOperations
from promptflow._utils.inputs_mapping_utils import apply_inputs_mapping
from promptflow._utils.load_data import load_data
from promptflow._utils.logger_utils import LoggerFactory
from promptflow.contracts.run_info import Status
from promptflow.contracts.run_mode import RunMode
from promptflow.exceptions import ErrorTarget, UserErrorException

logger = LoggerFactory.get_logger(name=__name__)


class ExperimentOrchestrator:
    """Experiment orchestrator, responsible for experiment running and status checking."""

    def __init__(self, client, experiment: Experiment = None):
        self.run_operations = client.runs
        self.experiment_operations = client._experiments
        self._client = client
        self.experiment = experiment
        self._nodes = {node.name: node for node in self.experiment.nodes} if experiment else {}
        # A key-value pair of node name and run info
        self._node_runs = {}

    def test(
        self, flow: Union[str, Path], template: ExperimentTemplate, inputs=None, environment_variables=None, **kwargs
    ):
        """Test flow in experiment.

        :param flow_path: Flow to test.
        :type flow_path: Union[str, Path]
        :param template: Experiment template to test.
        :type template: ~promptflow.entities.ExperimentTemplate
        :param inputs: Input parameters for flow.
        :type inputs: dict
        :param environment_variables: Environment variables for flow.
        :type environment_variables: dict
        """
        flow_path = Path(flow).resolve().absolute()
        logger.info(f"Testing flow {flow_path.as_posix()} in experiment {template._base_path.absolute().as_posix()}.")
        inputs, environment_variables = inputs or {}, environment_variables or {}
        # Find start nodes, must be flow nodes
        start_nodes = [
            node
            for node in template.nodes
            if node.type == ExperimentNodeType.FLOW
            and ProtectedFlow._get_flow_definition(node.path) == ProtectedFlow._get_flow_definition(flow_path)
        ]
        if not start_nodes:
            raise ExperimentValueError(f"Flow {flow_path.as_posix()} not found in experiment {template.dir_name!r}.")
        logger.info(f"Found start nodes {[node.name for node in start_nodes]} for experiment.")
        nodes_to_test = ExperimentHelper.resolve_nodes_to_execute(template, start_nodes)
        logger.info(f"Resolved nodes to test {[node.name for node in nodes_to_test]} for experiment.")
        # If inputs, use the inputs as experiment data, else read the first line in template data
        test_context = ExperimentTemplateTestContext(
            template,
            inputs=inputs,
            environment_variables=environment_variables,
            output_path=kwargs.get("output_path"),
            session=kwargs.get("session"),
        )

        for node in nodes_to_test:
            logger.info(f"Testing node {node.name}...")
            if node in start_nodes:
                # Start nodes inputs should be updated, as original value could be a constant without data reference.
                # Filter unknown key out to avoid warning (case: user input with eval key to override data).
                node.inputs = {**node.inputs, **{k: v for k, v in inputs.items() if k in node.inputs}}
            node_result = self._test_node(node, test_context)
            test_context.add_node_result(node.name, node_result)
        logger.info("Testing completed. See full logs at %s.", test_context.output_path.as_posix())
        return test_context.node_results

    def _test_node(self, node, test_context) -> Run:
        if node.type == ExperimentNodeType.FLOW:
            return self._test_flow_node(node, test_context)
        elif node.type == ExperimentNodeType.COMMAND:
            return self._test_command_node(node, test_context)
        raise ExperimentValueError(f"Unknown experiment node {node.name!r} type {node.type!r}")

    def _test_flow_node(self, node, test_context):
        # Resolve experiment related inputs
        inputs_mapping = ExperimentHelper.resolve_column_mapping(node.name, node.inputs, test_context.test_inputs)
        data, runs = ExperimentHelper.get_referenced_data_and_run(
            node.name, node.inputs, test_context.test_data, test_context.node_results
        )
        # Add data, run inputs/outputs to binding context for inputs mapping resolve.
        binding_context = {**{f"data.{k}": v for k, v in data.items()}, **{f"{k}.outputs": v for k, v in runs.items()}}
        binding_context.update(**{f"{k}.inputs": test_context.node_inputs.get(k, {}) for k in runs.keys()})
        logger.debug(f"Node {node.name!r} binding context {binding_context}.")
        # E.g. inputs_mapping: {'url': '${data.my_data.url}'}  inputs_data: {"data.my_data": {"url": "http://abc"}}
        inputs = apply_inputs_mapping(inputs=binding_context, inputs_mapping=inputs_mapping)
        logger.debug(f"Resolved node {node.name!r} inputs {inputs}.")
        test_context.add_node_inputs(node.name, inputs)
        node_context = test_context.get_node_context(node.name, is_flow=True, test=True)
        return self._client.flows.test(
            flow=node.path,
            environment_variables={**test_context.environment_variables, **node_context},
            inputs=inputs,
            output_path=test_context.output_path / node.name,
            dump_test_result=True,
            stream_output=False,
            run_id=test_context.node_name_to_id[node.name],
            session=test_context.session,
        )

    def _test_command_node(self, *args, **kwargs):
        raise NotImplementedError

    def start(self, nodes=None, from_nodes=None):
        """Start an execution of an experiment.

        Start an orchestrator to schedule node execution according to topological ordering.

        :param nodes: Nodes to be executed.
        :type nodes: list
        :param from_nodes: The branches in experiment to be executed.
        :type from_nodes: list
        :return: Experiment info.
        :rtype: ~promptflow.entities.Experiment
        """
        # Start experiment
        logger.info(f"Starting experiment {experiment.name}.")
        experiment.status = ExperimentStatus.IN_PROGRESS
        experiment.last_start_time = datetime.utcnow().isoformat()
        experiment.last_end_time = None
        self.experiment_operations.create_or_update(experiment)
        self._update_orchestrator_record(status=ExperimentStatus.IN_PROGRESS, pid=os.getpid())
        self._start_orchestrator(nodes=nodes, from_nodes=from_nodes)

    def async_start(self, executable_path=None, nodes=None, from_nodes=None):
        """Start an asynchronous execution of an experiment.

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
        if from_nodes:
            args = args + ["--from-nodes"] + from_nodes
        # Start an orchestrator process using detach mode
        logger.debug(f"Start experiment {self.experiment.name} in background.")
        _start_process_in_background(args, executable_path)
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

        def generate_node_mapping_by_nodes(from_nodes):
            all_node_edges_mapping = {node.name: prepare_edges(node) for node in self.experiment.nodes}
            node_edges_mapping, next_nodes = {node: all_node_edges_mapping[node] for node in from_nodes}, from_nodes
            while next_nodes:
                linked_nodes = set()
                for node in next_nodes:
                    in_degree_nodes = {k: v for k, v in all_node_edges_mapping.items() if node in v}
                    linked_nodes.update(set(in_degree_nodes.keys()) - set(node_edges_mapping.keys()))
                    node_edges_mapping.update(in_degree_nodes)
                next_nodes = linked_nodes
            all_nodes = set()
            for nodes in node_edges_mapping.values():
                all_nodes.update(nodes)
            pre_nodes = all_nodes - set(node_edges_mapping.keys())
            return node_edges_mapping, pre_nodes

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

        def check_in_degree_node_outputs(pre_nodes):
            """Check the input data of nodes already exists, it not return false."""
            node_runs = {
                node_name: next(filter(lambda x: x["status"] == ExperimentNodeRunStatus.COMPLETED, node_runs), None)
                for node_name, node_runs in self.experiment.node_runs.items()
            }
            is_in_degree_nodes_ready = True
            for in_degree_node in pre_nodes:
                is_in_degree_nodes_ready = in_degree_node in node_runs
                if node_runs.get(in_degree_node, None):
                    node_run_info = self.run_operations.get(node_runs[in_degree_node]["name"])
                    self._node_runs[in_degree_node] = node_run_info

                    output_path = node_run_info.properties.get("output_path", None)
                    is_in_degree_nodes_ready = is_in_degree_nodes_ready and Path(output_path).exists()
                else:
                    is_in_degree_nodes_ready = False
                    logger.warning(f"Cannot find the outputs of {in_degree_node}")
            return is_in_degree_nodes_ready

        def stop_process():
            """
            Post process of stop experiment. It will update status of all running node to canceled.
            And update status of experiment to terminated. Then terminate the orchestrator process.
            """
            executor.shutdown(wait=False)
            for future, node in future_to_node_run.items():
                if future.running():
                    # Update status of running nodes to canceled.
                    node.update_exp_run_node(status=ExperimentNodeRunStatus.CANCELED)
                    self.experiment._append_node_run(node.node.name, ORMRunInfo.get(node.name))
            # Update status experiment to terminated.
            self._update_orchestrator_record(status=ExperimentStatus.TERMINATED)
            # Terminate orchestrator process.
            sys.exit(1)

        if platform.system() == "Windows":
            import threading

            # Because of signal handler not works well in Windows, orchestrator starts a daemon thread
            # that creates named pipe to receive cancel signals from other processes.
            # Related issue of signal handler in Windows: https://bugs.python.org/issue26350
            pipe_thread = threading.Thread(
                target=_windows_stop_handler,
                args=(
                    self.experiment.name,
                    stop_process,
                ),
            )
            pipe_thread.daemon = True
            pipe_thread.start()
        else:

            def stop_handler(signum, frame):
                """
                Post-processing when the experiment is canceled.
                Terminate all executing nodes and update node status.
                """
                if signum == signal.SIGTERM:
                    stop_process()

            signal.signal(signal.SIGTERM, stop_handler)

        # TODO set max workers
        executor = ThreadPoolExecutor(max_workers=None)
        future_to_node_run = {}

        if from_nodes:
            # Executed from specified nodes
            # check in-degree nodes outputs exist
            node_edges_mapping, pre_nodes = generate_node_mapping_by_nodes(from_nodes)
            if not check_in_degree_node_outputs(pre_nodes):
                raise UserErrorException(f"The output(s) of in-degree for nodes {from_nodes} do not exist.")
            next_execute_nodes = [self._nodes[name] for name in from_nodes]
        elif nodes:
            # Executed specified nodes
            # check in-degree nodes outputs exist
            pre_nodes = set()
            node_mapping = {node.name: node for node in self.experiment.nodes}
            for node_name in nodes:
                pre_nodes.update(prepare_edges(node_mapping[node_name]))
            if not check_in_degree_node_outputs(pre_nodes):
                raise UserErrorException(f"The output(s) of in-degree of nodes {nodes} do not exist.")
            node_edges_mapping = {}
            next_execute_nodes = [self._nodes[name] for name in nodes]
        else:
            # Execute all nodes in experiment.
            node_edges_mapping = {node.name: prepare_edges(node) for node in self.experiment.nodes}
            logger.debug(f"Experiment nodes edges: {node_edges_mapping!r}")
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
                        # Get next executable nodes by completed nodes.
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
        """Stop in progress experiment.

        If experiment is not in progress, it will raise user error.
        In Linux, it will send terminate signal to orchestrator process. In Windows, it will pass signal by named pipe.
        When process receives the terminate signal, it will update running nodes to canceled and terminate the process.

        :return: Stopped experiment info.
        :rtype: ~promptflow.entities.Experiment
        """
        orchestrator = ORMOrchestrator.get(experiment_name=self.experiment.name)
        if orchestrator.status in [ExperimentStatus.NOT_STARTED, ExperimentStatus.QUEUING, ExperimentStatus.TERMINATED]:
            raise UserErrorException(
                target=ErrorTarget.CONTROL_PLANE_SDK,
                message="Experiment cannot be stopped if it is not started.",
            )

        _stop_orchestrator_process(orchestrator)

    @staticmethod
    def get_status(experiment_name):
        """Check the status of the orchestrator

        The status recorded in database and process status may be inconsistent.
        Need to check the orchestrator process status.

        :return: Orchestrator status.
        :rtype: str
        """

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
                        # This process is not the process used to start the orchestrator
                        # update experiment to terminated.
                        set_orchestrator_terminated()
                    return orm_orchestrator.status
                except psutil.NoSuchProcess:
                    # The process is terminated abnormally, update experiment to terminated.
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
        self.snapshot_id = _calculate_snapshot(self.column_mapping, self._input_data, self.flow)

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

    def _resolve_input_dirs(self):
        logger.info("Start resolve node %s input dirs.", self.node.name)
        # Get the node referenced data and run
        referenced_data, referenced_run = ExperimentHelper.get_referenced_data_and_run(
            node_name=self.node.name,
            column_mapping=self.column_mapping,
            experiment_data=self.experiment_data,
            experiment_runs=self.node_runs,
        )
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
            result.update(ExperimentHelper.resolve_binding_from_run(run_name, run_obj, self.run_operations))
        result = {k: str(Path(v).resolve()) for k, v in result.items() if v is not None}
        logger.debug(f"Resolved node {self.node.name} input dirs {result}.")
        return result

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
            run_info = self.run_operations.get(node_run.run_id)
            output_path = run_info.properties.get("output_path", None)
            if output_path and Path(output_path).exists():
                # TODO Whether need to link used node output folder in the experiment run folder
                logger.info(f"Reuse existing node run {run_info.name} for node {self.node.name}.")
                run_info.name = self.name
                return run_info
        # Update exp node run record
        self.update_exp_run_node(status=ExperimentNodeRunStatus.IN_PROGRESS)
        node_run_result = self._run_node()
        logger.info(f"Node {self.node.name} run {self.name} completed, outputs to {node_run_result._output_path}.")
        return node_run_result


class ExperimentTemplateContext:
    def __init__(self, template: ExperimentTemplate, environment_variables=None):
        """Context for experiment template.
        :param template: Template object to get definition of experiment.
        :param environment_variables: Environment variables specified for test.
        """
        self.template = template
        self.environment_variables = environment_variables or {}
        self._experiment_context = self._get_experiment_context()
        # Generate line run id for node
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        self.node_name_to_id = {node.name: f"{node.name}_attempt{timestamp}" for node in template.nodes}
        self.node_name_to_referenced_id = self._prepare_referenced_ids()

    def _prepare_referenced_ids(self):
        """Change name: [referenced_name] to name: [referenced_id]."""
        edges = ExperimentHelper.get_experiment_node_edges(self.template.nodes)
        result = {
            name: [self.node_name_to_id[referenced_name] for referenced_name in edges] for name, edges in edges.items()
        }
        logger.debug(f"Resolved node name to id mapping: {self.node_name_to_id}, referenced id mapping {result}.")
        return result

    def _get_experiment_context(self):
        """Get the experiment context required for trace."""
        if not self.template._source_path:
            return {}
        return {ExperimentContextKey.EXPERIMENT: Path(self.template._source_path).resolve().absolute().as_posix()}

    def get_node_context(self, node_name, is_flow, test=False):
        """Get the context for a node."""
        node_context = {**self._experiment_context}
        referenced_key = ExperimentContextKey.REFERENCED_LINE_RUN_ID if test else ExperimentContextKey.REFERENCED_RUN_ID
        referenced_ids = self.node_name_to_referenced_id.get(node_name, [])
        # Add reference context only for flow node
        if referenced_ids and is_flow:
            node_context[referenced_key] = next(iter(referenced_ids))
        global_context = os.environ.get(PF_TRACE_CONTEXT)
        # Expected global context: {"endpoint": "..", "attributes": {..}}
        global_context = json.loads(global_context) if global_context else {"endpoint": "", "attributes": {}}
        global_context["attributes"].update(node_context)
        return {PF_TRACE_CONTEXT: json.dumps(global_context)}


class ExperimentTemplateTestContext(ExperimentTemplateContext):
    def __init__(
        self, template: ExperimentTemplate, inputs=None, environment_variables=None, output_path=None, session=None
    ):
        """
        Test context for experiment template.
        :param template: Template object to get definition of experiment.
        :param inputs: User inputs when calling test command.
        :param environment_variables: Environment variables specified for test.
        :param output_path: The custom output path.
        :param session: The session id for the test trace.
        """
        super().__init__(template, environment_variables)
        self.node_results = {}  # E.g. {'main': {'category': 'xx', 'evidence': 'xx'}}
        self.node_inputs = {}  # E.g. {'main': {'url': 'https://abc'}}
        self.test_data = ExperimentHelper.prepare_test_data(inputs, template)
        self.test_inputs = {input.name: input.default for input in template.inputs}
        # TODO: Update session part after test session is supported
        if output_path:
            self.output_path = Path(output_path)
        else:
            self.output_path = (
                Path(tempfile.gettempdir()) / PROMPT_FLOW_DIR_NAME / "sessions/default" / template.dir_name
            )
        # All test run in experiment should use same session
        self.session = session or uuid.uuid4()

    def add_node_inputs(self, name, inputs):
        self.node_inputs[name] = inputs

    def add_node_result(self, name, result):
        self.node_results[name] = result


class ExperimentHelper:
    @staticmethod
    def prepare_test_data(inputs, template: ExperimentTemplate) -> dict:
        """Prepare test data.
        If inputs is given, use it for all test data.
        Else, read the first line of template data path for test."""
        template_test_data = {}
        for data in template.data:
            data_line = inputs or next(iter(load_data(local_path=data.path)), None)
            if not data_line:
                raise ExperimentValueError(f"Experiment data {data.name!r} is empty.")
            template_test_data[data.name] = data_line
        return template_test_data

    @staticmethod
    def get_referenced_data_and_run(
        node_name: str, column_mapping: dict, experiment_data: dict, experiment_runs: dict
    ) -> tuple:
        """Get the node referenced data and runs from dict."""
        data, run = {}, {}
        for value in column_mapping.values():
            if not isinstance(value, str):
                continue
            if value.startswith("${data."):
                name = value.split(".")[1].replace("}", "")
                if name not in experiment_data:
                    raise ExperimentValueError(
                        f"Node {node_name!r} inputs {value!r} related experiment data {name!r} not found."
                    )
                data[name] = experiment_data[name]
            elif value.startswith("${"):
                name = value.split(".")[0].replace("${", "")
                if name not in experiment_runs:
                    raise ExperimentValueError(
                        f"Node {node_name!r} inputs {value!r} related experiment run {name!r} not found."
                    )
                run[name] = experiment_runs[name]
        return data, run

    @staticmethod
    def resolve_column_mapping(node_name: str, column_mapping: dict, experiment_inputs: dict):
        """Resolve column mapping with experiment inputs to constant values."""
        logger.info(f"Start resolve node {node_name!r} column mapping.")
        if not column_mapping:
            return {}
        resolved_mapping = {}
        for name, value in column_mapping.items():
            if not isinstance(value, str) or not value.startswith("${inputs."):
                resolved_mapping[name] = value
                continue
            input_name = value.split(".")[1].replace("}", "")
            if input_name not in experiment_inputs:
                raise ExperimentValueError(
                    f"Node {node_name!r} inputs {value!r} related experiment input {input_name!r} not found."
                )
            resolved_mapping[name] = experiment_inputs[input_name].default
        logger.debug(f"Resolved node {node_name!r} column mapping {resolved_mapping}.")
        return resolved_mapping

    @staticmethod
    def _is_node_reference(value):
        """Check if value is a node reference."""
        return (
            isinstance(value, str)
            and value.startswith("${")
            and not value.startswith("${data.")
            and not value.startswith("${inputs.")
        )

    @staticmethod
    def _prepare_single_node_edges(node):
        """Prepare single node name to referenced node name edges mapping."""
        node_names = set()
        for input_value in node.inputs.values():
            if not isinstance(input_value, str):
                continue
            if ExperimentHelper._is_node_reference(input_value):
                referenced_node_name = input_value.split(".")[0].replace("${", "")
                node_names.add(referenced_node_name)
        return node_names

    @staticmethod
    def get_experiment_node_edges(nodes):
        """Get experiment node edges mapping."""
        return {node.name: ExperimentHelper._prepare_single_node_edges(node) for node in nodes}

    @staticmethod
    def resolve_nodes_to_execute(experiment, start_nodes=None):
        """Resolve node to execute and ensure nodes order in experiment."""

        def _remove_nodes_from_active_edges(nodes_to_remove):
            for node in nodes_to_remove:
                for referenced_nodes in active_edges.values():
                    referenced_nodes.discard(node.name)
                del active_edges[node.name]

        def _can_remove_node(node):
            # No start nodes specified, no edge linked, then node is available.
            if not start_nodes:
                if node.name in active_edges and len(active_edges[node.name]) == 0:
                    return True
                return False
            # Start nodes specified, successor nodes of resolved nodes are available, edges are required.
            if node.name not in active_edges or len(edges[node.name]) == 0:
                return False
            # All predecessor nodes are resolved, then node is available.
            if all(referenced_node not in active_edges for referenced_node in edges[node.name]):
                return True
            return False

        # Perform topological sort to ensure nodes order
        nodes = experiment.nodes
        resolved_nodes, start_nodes = [], start_nodes or []
        edges = {node.name: ExperimentHelper._prepare_single_node_edges(node) for node in nodes}
        active_edges = copy.deepcopy(edges)
        # If start nodes specified, preprocessing them.
        _remove_nodes_from_active_edges(start_nodes)
        resolved_nodes.extend(start_nodes)
        logger.debug(f"Experiment start node {[node.name for node in start_nodes]}, nodes edges: {active_edges!r}")

        while True:
            available_nodes = [node for node in nodes if _can_remove_node(node)]
            logger.debug(f"Experiment available nodes: {[node.name for node in available_nodes]!r}")
            if not available_nodes:
                break
            _remove_nodes_from_active_edges(available_nodes)
            resolved_nodes.extend(available_nodes)
        # If no start nodes specified, all nodes should be visited.
        if not start_nodes and len(resolved_nodes) != len(nodes):
            raise ExperimentHasCycle(f"Experiment has circular dependency {active_edges!r}")
        logger.debug(f"Experiment nodes resolved: {[node.name for node in resolved_nodes]}")
        return resolved_nodes

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
            return_code = ExperimentCommandExecutor.run(
                command=command, cwd=run.flow, log_path=local_storage.logger.file_path
            )
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
    def run(command: str, cwd: str, log_path: Path):
        """Start a subprocess to run the command"""
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
        ExperimentOrchestrator(client, experiment=experiment).start(nodes=args.nodes, from_nodes=args.from_nodes)
