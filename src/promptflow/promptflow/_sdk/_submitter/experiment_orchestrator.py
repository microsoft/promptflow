# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict

from promptflow._sdk._configuration import Configuration
from promptflow._sdk._constants import ExperimentNodeType, ExperimentStatus, FlowRunProperties, RunTypes
from promptflow._sdk._errors import ExperimentCommandRunError, ExperimentHasCycle, ExperimentValueError
from promptflow._sdk._submitter import RunSubmitter
from promptflow._sdk._submitter.utils import SubmitterHelper
from promptflow._sdk.entities import Run
from promptflow._sdk.entities._experiment import Experiment
from promptflow._sdk.operations import RunOperations
from promptflow._sdk.operations._experiment_operations import ExperimentOperations
from promptflow._sdk.operations._local_storage_operations import LocalStorageOperations
from promptflow._utils.logger_utils import LoggerFactory
from promptflow.contracts.run_info import Status
from promptflow.contracts.run_mode import RunMode
from promptflow.exceptions import UserErrorException

logger = LoggerFactory.get_logger(name=__name__)


class ExperimentOrchestrator:
    """Experiment orchestrator, responsible for experiment running."""

    def __init__(self, run_operations: RunOperations, experiment_operations: ExperimentOperations):
        self.run_operations = run_operations
        self.experiment_operations = experiment_operations
        self.run_submitter = ExperimentRunSubmitter(run_operations)
        self.command_submitter = ExperimentCommandSubmitter(run_operations)

    def start(self, experiment: Experiment, **kwargs):
        """Start an experiment.

        :param experiment: Experiment to start.
        :type experiment: ~promptflow.entities.Experiment
        :param kwargs: Keyword arguments.
        :type kwargs: Any
        """
        # Start experiment
        logger.info(f"Starting experiment {experiment.name}.")
        experiment.status = ExperimentStatus.IN_PROGRESS
        experiment.last_start_time = datetime.utcnow().isoformat()
        experiment.last_end_time = None
        self.experiment_operations.create_or_update(experiment)

        # Ensure nodes order
        resolved_nodes = self._ensure_nodes_order(experiment.nodes)

        # Run nodes
        run_dict = {}
        try:
            for node in resolved_nodes:
                logger.info(f"Running node {node.name}.")
                run = self._run_node(node, experiment, run_dict)
                # Update node run to experiment
                experiment._append_node_run(node.name, run)
                self.experiment_operations.create_or_update(experiment)
                run_dict[node.name] = run
                logger.info(f"Node {node.name} run {run.name} completed, outputs to {run._output_path}.")
        except Exception as e:
            logger.error(f"Running experiment {experiment.name} failed with error {e}.")
        finally:
            # End experiment
            logger.info(f"Terminating experiment {experiment.name}.")
            experiment.status = ExperimentStatus.TERMINATED
            experiment.last_end_time = datetime.utcnow().isoformat()
            return self.experiment_operations.create_or_update(experiment)

    def _ensure_nodes_order(self, nodes):
        # Perform topological sort to ensure nodes order
        resolved_nodes = []

        def _prepare_edges(node):
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

        edges = {node.name: _prepare_edges(node) for node in nodes}
        logger.debug(f"Experiment nodes edges: {edges!r}")

        while len(resolved_nodes) != len(nodes):
            action = False
            for node in nodes:
                if node.name not in edges:
                    continue
                if len(edges[node.name]) != 0:
                    continue
                action = True
                resolved_nodes.append(node)
                del edges[node.name]
                for referenced_nodes in edges.values():
                    referenced_nodes.discard(node.name)
                break
            if not action:
                raise ExperimentHasCycle(f"Experiment has circular dependency {edges!r}")

        logger.debug(f"Experiment nodes resolved order: {[node.name for node in resolved_nodes]}")
        return resolved_nodes

    def _run_node(self, node, experiment, run_dict) -> Run:
        if node.type == ExperimentNodeType.FLOW:
            return self._run_flow_node(node, experiment, run_dict)
        elif node.type == ExperimentNodeType.COMMAND:
            return self._run_command_node(node, experiment, run_dict)
        raise ExperimentValueError(f"Unknown experiment node {node.name!r} type {node.type!r}")

    def _run_flow_node(self, node, experiment, run_dict):
        run_output_path = (Path(experiment._output_dir) / "runs" / node.name).resolve().absolute().as_posix()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        run = ExperimentRun(
            node_name=node.name,
            experiment=experiment,
            experiment_runs=run_dict,
            # Use node name as prefix for run name?
            name=f"{node.name}_attempt{timestamp}",
            display_name=node.display_name or node.name,
            column_mapping=node.inputs,
            variant=node.variant,
            flow=node.path,
            connections=node.connections,
            environment_variables=node.environment_variables,
            # Config run output path to experiment output folder
            config=Configuration(overrides={Configuration.RUN_OUTPUT_PATH: run_output_path}),
        )
        logger.debug(f"Creating run {run.name}")
        return self.run_submitter.submit(run)

    def _run_command_node(self, node, experiment, run_dict):
        run_output_path = (Path(experiment._output_dir) / "runs" / node.name).resolve().absolute().as_posix()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        run = ExperimentRun(
            type=RunTypes.COMMAND,
            node_name=node.name,
            experiment=experiment,
            experiment_runs=run_dict,
            name=f"{node.name}_attempt{timestamp}",
            display_name=node.display_name or node.name,
            column_mapping=node.inputs,
            # Use command code path as flow path
            flow=node.code,
            outputs=node.outputs,
            command=node.command,
            environment_variables=node.environment_variables,
            config=Configuration(overrides={Configuration.RUN_OUTPUT_PATH: run_output_path}),
        )
        logger.debug(f"Creating run {run.name}")
        return self.command_submitter.submit(run)


class ExperimentRun(Run):
    """Experiment run, includes experiment running context, like data, inputs and runs."""

    def __init__(self, experiment, node_name, experiment_runs: Dict[str, "ExperimentRun"], **kwargs):
        self.node_name = node_name
        self.experiment = experiment
        self.experiment_data = {data.name: data for data in experiment.data}
        self.experiment_inputs = {input.name: input for input in experiment.inputs}
        self.experiment_runs = experiment_runs
        super().__init__(**kwargs)
        self._resolve_column_mapping()

    def _resolve_column_mapping(self):
        """Resolve column mapping with experiment inputs to constant values."""
        logger.info(f"Start resolve node {self.node_name!r} column mapping.")
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
        logger.debug(f"Resolved node {self.node_name!r} column mapping {resolved_mapping}.")
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
                if name not in self.experiment_runs:
                    raise ExperimentValueError(
                        f"Node {self.display_name!r} inputs {value!r} related experiment run {name!r} not found."
                    )
                run[name] = self.experiment_runs[name]
        return data, run


class ExperimentRunSubmitterHelper:
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


class ExperimentRunSubmitter(RunSubmitter):
    """Experiment run submitter, override some function from RunSubmitter as experiment run could be different."""

    @classmethod
    def _validate_inputs(cls, run: Run):
        # Do not validate run/data field, as we will resolve them in _resolve_input_dirs.
        return

    def _resolve_input_dirs(self, run: ExperimentRun):
        logger.info("Start resolve node %s input dirs.", run.node_name)
        logger.debug(f"Experiment context: {run.experiment_data}, {run.experiment_runs}, inputs: {run.column_mapping}")
        # Get the node referenced data and run
        referenced_data, referenced_run = run._get_referenced_data_and_run()
        if len(referenced_data) > 1:
            raise ExperimentValueError(f"Experiment has multiple data inputs {referenced_data}, only 1 is expected.")
        if len(referenced_run) > 1:
            raise ExperimentValueError(f"Experiment has multiple run inputs {referenced_run}, only 1 is expected.")
        (data_name, data_obj) = next(iter(referenced_data.items())) if referenced_data else (None, None)
        (run_name, run_obj) = next(iter(referenced_run.items())) if referenced_run else (None, None)
        logger.debug(f"Resolve node {run.node_name} referenced data {data_name!r}, run {run_name!r}.")
        # Build inputs from experiment data and run
        result = {}
        if data_obj:
            result.update({f"data.{data_name}": data_obj.path})
        if run_obj:
            result.update(ExperimentRunSubmitterHelper.resolve_binding_from_run(run_name, run_obj, self.run_operations))
        result = {k: str(Path(v).resolve()) for k, v in result.items() if v is not None}
        logger.debug(f"Resolved node {run.node_name} input dirs {result}.")
        return result


class ExperimentCommandSubmitter:
    """Experiment command submitter, responsible for experiment command running."""

    def __init__(self, run_operations: RunOperations):
        self.run_operations = run_operations

    def submit(self, run: ExperimentRun, **kwargs):
        """Submit an experiment command run.

        :param run: Experiment command to submit.
        :type run: ~promptflow.entities.Run
        """
        local_storage = LocalStorageOperations(run, run_mode=RunMode.SingleNode)
        self._submit_command_run(run=run, local_storage=local_storage)
        return self.run_operations.get(name=run.name)

    def _resolve_inputs(self, run: ExperimentRun):
        """Resolve binding inputs to constant values."""
        # e.g. "input_path": "${data.my_data}" -> "${inputs.input_path}": "real_data_path"
        logger.info("Start resolve node %s inputs.", run.node_name)
        data, runs = run._get_referenced_data_and_run()
        # prepare "${data.my_data}": real_data_path
        binding_dict = {"${data.%s}" % name: val.path for name, val in data.items()}
        # prepare "${run.outputs}": run_outputs_path, "${run.inputs}": run_inputs_path
        for name, val in runs.items():
            binding_dict.update(
                {
                    "${%s}" % k: v
                    for k, v in ExperimentRunSubmitterHelper.resolve_binding_from_run(
                        name, val, self.run_operations
                    ).items()
                }
            )
        logger.debug(f"Resolved node {run.node_name} binding inputs {binding_dict}.")
        # resolve inputs
        resolved_inputs = {}
        for name, value in run.column_mapping.items():
            if not isinstance(value, str) or not value.startswith("${"):
                resolved_inputs[name] = value
                continue
            # my_input: "${run.outputs}" -> my_input: run_outputs_path
            if value in binding_dict:
                resolved_inputs[name] = binding_dict[value]
                continue
            logger.warning(
                f"Possibly invalid partial input value binding {value!r} found for node {run.node_name!r}. "
                "Only full binding is supported for command node. For example: ${data.my_data}, ${main_node.outputs}."
            )
            resolved_inputs[name] = value
        logger.debug(f"Resolved node {run.node_name} inputs {resolved_inputs}.")
        return resolved_inputs

    def _resolve_outputs(self, run: ExperimentRun):
        """Resolve outputs to real path."""
        # e.g. "output_path": "${outputs.my_output}" -> "${outputs.output_path}": "real_output_path"
        logger.info("Start resolve node %s outputs.", run.node_name)
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
        logger.debug(f"Resolved node {run.node_name} outputs {resolved_outputs}.")
        return resolved_outputs

    def _resolve_command(self, run: ExperimentRun, inputs: dict, outputs: dict):
        """Resolve command to real command."""
        logger.info("Start resolve node %s command.", run.node_name)
        # resolve command
        resolved_command = run._command
        # replace inputs
        for name, value in inputs.items():
            resolved_command = resolved_command.replace(f"${{inputs.{name}}}", str(value))
        # replace outputs
        for name, value in outputs.items():
            resolved_command = resolved_command.replace(f"${{outputs.{name}}}", str(value))
        logger.debug(f"Resolved node {run.node_name} command {resolved_command}.")
        if "${" in resolved_command:
            logger.warning(
                f"Possibly unresolved command value binding found for node {run.node_name!r}. "
                f"Resolved command: {resolved_command}. Please check your command again."
            )
        return resolved_command

    def _submit_command_run(self, run: ExperimentRun, local_storage: LocalStorageOperations) -> dict:
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
