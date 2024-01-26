# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from datetime import datetime
from pathlib import Path

from promptflow._sdk._configuration import Configuration
from promptflow._sdk._constants import ExperimentNodeType, ExperimentStatus
from promptflow._sdk._errors import ExperimentHasCycle, ExperimentValueError
from promptflow._sdk._submitter import RunSubmitter
from promptflow._sdk.entities import Run
from promptflow._sdk.entities._experiment import Experiment
from promptflow._sdk.operations import RunOperations
from promptflow._sdk.operations._experiment_operations import ExperimentOperations
from promptflow._utils.logger_utils import LoggerFactory

logger = LoggerFactory.get_logger(name=__name__)


class ExperimentOrchestrator:
    """Experiment orchestrator, responsible for experiment running."""

    def __init__(self, run_operations: RunOperations, experiment_operations: ExperimentOperations):
        self.run_operations = run_operations
        self.experiment_operations = experiment_operations
        self.run_submitter = ExperimentRunSubmitter(run_operations)

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
                if input_value.startswith("${") and not input_value.startswith("${data."):
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
        elif node.type == ExperimentNodeType.CODE:
            return self._run_script_node(node, experiment)
        raise ExperimentValueError(f"Unknown experiment node {node.name!r} type {node.type!r}")

    def _run_flow_node(self, node, experiment, run_dict):
        run_output_path = (Path(experiment._output_dir) / "runs" / node.name).resolve().absolute().as_posix()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        run = ExperimentRun(
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

    def _run_script_node(self, node, experiment):
        pass


class ExperimentRun(Run):
    """Experiment run, includes experiment running context, like data, inputs and runs."""

    def __init__(self, experiment, experiment_runs, **kwargs):
        self.experiment = experiment
        self.experiment_data = {data.name: data for data in experiment.data}
        self.experiment_inputs = {input.name: input for input in experiment.inputs}
        self.experiment_runs = experiment_runs
        super().__init__(**kwargs)
        self._resolve_column_mapping()

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


class ExperimentRunSubmitter(RunSubmitter):
    """Experiment run submitter, override some function from RunSubmitter as experiment run could be different."""

    @classmethod
    def _validate_inputs(cls, run: Run):
        # Do not validate run/data field, as we will resolve them in _resolve_input_dirs.
        return

    def _resolve_input_dirs(self, run: ExperimentRun):
        logger.info("Start resolve node %s input dirs.", run.name)
        logger.debug(f"Experiment context: {run.experiment_data}, {run.experiment_runs}, inputs: {run.column_mapping}")
        # Get the node referenced data and run
        data_name, run_name = None, None
        inputs_mapping = run.column_mapping
        for value in inputs_mapping.values():
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
        logger.debug(f"Resolve node {run.name} referenced data {data_name!r}, run {run_name!r}.")
        # Build inputs from experiment data and run
        result = {}
        if data_name in run.experiment_data and run.experiment_data[data_name].path:
            result.update({f"data.{data_name}": run.experiment_data[data_name].path})
        if run_name in run.experiment_runs:
            result.update(
                {
                    f"{run_name}.outputs": self.run_operations._get_outputs_path(run.experiment_runs[run_name]),
                    # to align with cloud behavior, run.inputs should refer to original data
                    f"{run_name}.inputs": self.run_operations._get_data_path(run.experiment_runs[run_name]),
                }
            )
        result = {k: str(Path(v).resolve()) for k, v in result.items() if v is not None}
        logger.debug(f"Resolved node {run.name} input dirs {result}.")
        return result
