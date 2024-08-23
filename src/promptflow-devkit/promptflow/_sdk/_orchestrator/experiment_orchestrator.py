# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import argparse
import copy
import json
import os
import platform
import re
import signal
import subprocess
import sys
import tempfile
import uuid
from concurrent import futures
from concurrent.futures import ThreadPoolExecutor
from dataclasses import is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Union

import psutil

from promptflow._sdk._constants import (
    CHAT_GROUP_REFERENCE_NAME,
    CONVERSATION_HISTORY,
    EXP_NODE_TYPE_2_RUN_TYPE,
    PF_TRACE_CONTEXT,
    PF_TRACE_CONTEXT_ATTR,
    PROMPT_FLOW_DIR_NAME,
    ContextAttributeKey,
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
from promptflow._sdk._orchestrator import RunSubmitter
from promptflow._sdk._orchestrator.utils import (
    SubmitterHelper,
    _calculate_snapshot,
    _set_up_experiment_log_handler,
    _start_process_in_background,
    _stop_orchestrator_process,
    _windows_stop_handler,
)
from promptflow._sdk._orm.experiment import Experiment as ORMExperiment
from promptflow._sdk._orm.experiment_node_run import ExperimentNodeRun as ORMExperimentNodeRun
from promptflow._sdk._orm.orchestrator import Orchestrator as ORMOrchestrator
from promptflow._sdk._orm.run_info import RunInfo as ORMRunInfo
from promptflow._sdk._utilities.general_utils import overwrite_null_std_logger
from promptflow._sdk.entities import Run
from promptflow._sdk.entities._experiment import CommandNode, Experiment, ExperimentTemplate, FlowNode
from promptflow._sdk.operations import RunOperations
from promptflow._sdk.operations._local_storage_operations import LocalStorageOperations
from promptflow._utils.flow_utils import resolve_flow_path
from promptflow._utils.inputs_mapping_utils import apply_inputs_mapping
from promptflow._utils.load_data import load_data
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow.contracts.run_info import Status
from promptflow.contracts.run_mode import RunMode
from promptflow.exceptions import ErrorTarget, UserErrorException

overwrite_null_std_logger()
logger = get_cli_sdk_logger()


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
        self,
        template: ExperimentTemplate,
        inputs=None,
        **kwargs,
    ):
        """Test experiment.

        :param template: Experiment template to test.
        :type template: ~promptflow.entities.ExperimentTemplate
        :param inputs: Input parameters for experiment.
        :type inputs: dict
        """
        logger.info(f"Testing experiment {template._base_path.absolute().as_posix()}.")
        start_nodes = [node for node in template.nodes if len(ExperimentHelper._prepare_single_node_edges(node)) == 0]
        if not start_nodes:
            raise ExperimentValueError(f"Not found start node in experiment {template.dir_name!r}.")

        inputs = inputs or {}
        logger.info(f"Found start nodes {[node.name for node in start_nodes]} for experiment.")
        nodes_to_test = ExperimentHelper.resolve_nodes_to_execute(template, start_nodes)
        logger.info(f"Resolved nodes to test {[node.name for node in nodes_to_test]} for experiment.")
        # If inputs, override experiment inputs.
        test_context = ExperimentTemplateTestContext(
            template,
            override_inputs=inputs,
            output_path=kwargs.get("output_path"),
            session=kwargs.get("session"),
        )

        for node in nodes_to_test:
            logger.info(f"Testing node {node.name}...")
            node_result = self._test_node(node, test_context)
            test_context.add_node_result(node.name, node_result)
        logger.info("Testing completed. See full logs at %s.", test_context.output_path.as_posix())
        return test_context.node_results

    def test_flow(
        self,
        template: ExperimentTemplate,
        flow: Union[str, Path] = None,
        inputs=None,
        environment_variables=None,
        **kwargs,
    ):
        """Test flow in experiment.

        :param flow_path: Flow to test.
        :type flow_path: Union[str, Path]
        :param template: Experiment template to test.
        :type template: ~promptflow.entities.ExperimentTemplate
        :param inputs: Input parameters for flow.
        :type inputs: dict
        :param environment_variables: Environment variables when test flow in experiment.
        :type environment_variables: dict
        """
        if flow is not None:
            flow_path = Path(flow).resolve().absolute()
            logger.info(
                f"Testing flow {flow_path.as_posix()} in experiment " f"{template._base_path.absolute().as_posix()}."
            )
            # Find start nodes, must be flow nodes
            start_nodes = [
                node
                for node in template.nodes
                if node.type == ExperimentNodeType.FLOW and resolve_flow_path(node.path) == resolve_flow_path(flow_path)
            ]
            if not start_nodes:
                raise ExperimentValueError(
                    f"Flow {flow_path.as_posix()} not found in experiment {template.dir_name!r}."
                )
        else:
            logger.info(f"Testing experiment {template._base_path.absolute().as_posix()}.")
            start_nodes = [
                node
                for node in template.nodes
                if len(ExperimentHelper._prepare_single_node_edges(node)) == 0 and node.type == ExperimentNodeType.FLOW
            ]
            if not start_nodes:
                raise ExperimentValueError(f"Not found start node in experiment {template.dir_name!r}.")

        inputs, environment_variables = inputs or {}, environment_variables or {}
        logger.info(f"Found start nodes {[node.name for node in start_nodes]} for experiment.")
        nodes_to_test = ExperimentHelper.resolve_nodes_to_execute(template, start_nodes)
        logger.info(f"Resolved nodes to test {[node.name for node in nodes_to_test]} for experiment.")
        context = kwargs.pop("context", None)
        if context is not None:
            return self._test_with_ui(
                context, template, nodes_to_test, start_nodes, inputs, environment_variables, **kwargs
            )
        # If inputs, use the inputs as experiment data, else read the first line in template data
        test_context = ExperimentTemplateTestContext(
            template,
            override_data=inputs,
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

    def _test_with_ui(
        self,
        context: dict,
        template: ExperimentTemplate,
        nodes_to_test,
        start_nodes,
        inputs=None,
        environment_variables=None,
        **kwargs,
    ):
        # The api is used for ux calling pfs. We need the api to deal with skip flow or overwrite unbinding flow
        # input scenario
        context_flow = context.get("node", None)
        context_run_id = context.get("run_id", None)

        skip_node_name = None
        override_node_name = None
        main_node_name = None
        if context_flow:
            for node in nodes_to_test:
                # only support skip/override the first flow node which matches the ux passed flow path for now.
                if Path(context_flow).as_posix() == Path(node.path).as_posix():
                    if "outputs" in context:
                        skip_node_name = node.name
                    else:
                        override_node_name = node.name
                        main_node_name = node.name if context_run_id else None
                    break

        # If inputs, use the inputs as experiment data, else read the first line in template data
        test_context = ExperimentTemplateTestContext(
            template,
            override_data=inputs,
            environment_variables=environment_variables,
            output_path=kwargs.get("output_path"),
            session=kwargs.get("session"),
            context_run_id=context_run_id,
            context_node_name=skip_node_name if skip_node_name else main_node_name,
        )

        for node in nodes_to_test:
            if skip_node_name and skip_node_name == node.name:
                test_context.add_node_result(node.name, context.get("outputs", {}))
                continue
            logger.info(f"Testing node {node.name}...")
            if node in start_nodes:
                if override_node_name and override_node_name == node.name:
                    node.inputs = {**node.inputs, **{k: v for k, v in context.get("inputs", {}).items()}}
                    node.init = {**node.init, **{k: v for k, v in context.get("init", {}).items()}}
                else:
                    # Start nodes inputs should be updated, as original value could be a constant without data
                    # reference. Filter unknown key out to avoid warning (case: user input with eval key to override
                    # data).
                    node.inputs = {**node.inputs, **{k: v for k, v in inputs.items() if k in node.inputs}}
            node_result = self._test_node(node, test_context)
            test_context.add_node_result(node.name, node_result)
        logger.info("Testing completed. See full logs at %s.", test_context.output_path.as_posix())
        if skip_node_name and skip_node_name in test_context.node_results:
            test_context.node_results.pop(skip_node_name)
        return test_context.node_results

    def _test_node(self, node, test_context):
        if node.type == ExperimentNodeType.FLOW:
            return self._test_flow_node(node, test_context)
        elif node.type == ExperimentNodeType.COMMAND:
            return self._test_command_node(node, test_context)
        elif node.type == ExperimentNodeType.CHAT_GROUP:
            return self._test_chat_group_node(node, test_context)
        raise ExperimentValueError(f"Unknown experiment node {node.name!r} type {node.type!r}")

    def _resolve_command_node_outputs_for_test(self, used_node_results, node, test_context):
        """Read the first line data from command node outputs folder for test."""
        # Example: {'node': {"output_path": "a/b/c"}} -> {'node': {"output_path": {"data1": "abc"}}}
        resolved_results = {}
        from promptflow._constants import MessageFormatType
        from promptflow.batch._batch_inputs_processor import BatchInputsProcessor

        # Note: Hardcode to basic now.
        processor = BatchInputsProcessor(
            working_dir=node.path, flow_inputs=None, message_format=MessageFormatType.BASIC
        )
        for referenced_node_name, node_results in used_node_results.items():
            if referenced_node_name not in test_context.command_node_names:
                resolved_results[f"{referenced_node_name}.outputs"] = node_results
                continue
            logger.info(
                f"{referenced_node_name!r} is a command node, "
                f"resolving test inputs from outputs for {node.name} node execution."
            )
            # Example node results: {"output1": [{"url": xx}], "output2": [{"number": 111]}}
            node_results = processor._resolve_input_data_and_check(input_dirs=node_results)
            # Take the first line of data
            resolved_results.update({f"{referenced_node_name}.outputs.{k}": v[0] for k, v in node_results.items()})
        logger.debug(f"Resolved command node {node.name!r} outputs {resolved_results}.")
        return resolved_results

    def _test_flow_node(self, node: FlowNode, test_context):
        # Resolve experiment related inputs
        inputs_mapping = ExperimentHelper.resolve_column_mapping(node.name, node.inputs, test_context.test_inputs)
        data, runs = ExperimentHelper.get_referenced_data_and_run(
            node.name, node.type, node.inputs, test_context.test_data, test_context.node_results
        )
        # Read first line data for command node run results
        referenced_node_results = self._resolve_command_node_outputs_for_test(runs, node, test_context)
        # Add data, run inputs/outputs to binding context for inputs mapping resolve.
        binding_context = {**{f"data.{k}": v for k, v in data.items()}, **referenced_node_results}
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
            allow_generator_output=False,
            stream_output=False,
            run_id=test_context.node_name_to_id[node.name],
            session=test_context.session,
            init=node.init,
        )

    def _test_command_node(self, node: CommandNode, test_context):
        logger.debug("Dumping data and node test output to file for command node testing.")

        def _dump_data(data_dict, base_dir, is_data=False):
            updated_data_dict = {}
            base_dir = Path(base_dir)
            base_dir.mkdir(parents=True, exist_ok=True)
            for name, data in data_dict.items():
                if name in test_context.command_node_names:
                    # Command node outputs already in files
                    continue
                file_path = base_dir / f"{name}.json"
                name = f"data.{name}" if is_data else f"{name}.outputs"
                updated_data_dict[name] = file_path.as_posix()
                # DO NOT reuse file here as user could test multiple times
                with open(file_path, "w") as f:
                    json.dump(data, f)
            return updated_data_dict

        # Dump data and node results to file
        # {'my_data': {'url': 'https://www.youtube.com/watch?v=kYqRtjDBci8'}} -> {'data.my_data': <path>}
        data_inputs = _dump_data(test_context.test_data, test_context.output_path / "data", is_data=True)
        # {'node': {'url': 'https://www.youtube.com/watch?v=kYqRtjDBci8'}} -> {'node': <path>}
        node_results = _dump_data(test_context.node_results, test_context.output_path / "outputs")
        # resolve inputs & outputs for command preparing
        # Merge experiment data, experiment inputs, and node results
        all_inputs = {**data_inputs, **node_results, **{f"inputs.{k}": v for k, v in test_context.test_inputs.items()}}
        # e.g. input_path: ${data.my_data} -> ${inputs.input_path}: real_data_path
        inputs = ExperimentCommandSubmitter._resolve_inputs(node.name, node.inputs, all_inputs)
        node_output_dir = test_context.output_path / node.name
        logger.debug("Node %s base output dir %s.", node.name, node_output_dir)
        outputs = ExperimentCommandSubmitter._resolve_outputs(node.name, node.outputs, node_output_dir)
        # replace to command
        command = ExperimentCommandSubmitter._resolve_command(node.name, node.command, inputs, outputs)
        # Resolve connection env var on node
        environment_variables = {**node.environment_variables, **test_context.environment_variables}
        SubmitterHelper.resolve_environment_variables(environment_variables=environment_variables)
        SubmitterHelper.init_env(environment_variables=environment_variables)
        ExperimentCommandExecutor.run(command, node.code, test_context.output_path / "log.txt")
        # Return dir path as command node testing result
        return outputs

    def _test_chat_group_node(self, node, test_context):
        from promptflow._sdk.entities._chat_group._chat_group import ChatGroup

        chat_group = ChatGroup._from_node(node, test_context)
        logger.debug(f"Invoking chat group node {node.name!r}.")
        chat_group.invoke()
        return chat_group.conversation_history

    def start(self, nodes=None, from_nodes=None, attempt=None, **kwargs):
        """Start an execution of nodes.

        Start an orchestrator to schedule node execution according to topological ordering.

        :param nodes: Nodes to be executed.
        :type nodes: list
        :param from_nodes: The branches in experiment to be executed.
        :type from_nodes: list
        :param attempt: The number of attempts, it's used to record the experiment execution log.
        :type attempt: int
        :return: Experiment info.
        :rtype: ~promptflow.entities.Experiment
        """
        # Start experiment
        experiment = self.experiment
        file_handler, index = _set_up_experiment_log_handler(experiment_path=self.experiment._output_dir, index=attempt)
        logger.addHandler(file_handler._stream_handler)
        try:
            logger.info(f"Starting experiment {experiment.name}.")
            experiment.status = ExperimentStatus.IN_PROGRESS
            experiment.last_start_time = datetime.utcnow().isoformat()
            experiment.last_end_time = None
            context = ExperimentTemplateContext(experiment, session=kwargs.get("session"))
            self.experiment_operations.create_or_update(experiment)
            self._update_orchestrator_record(status=ExperimentStatus.IN_PROGRESS, pid=os.getpid())
            self._start_orchestrator(nodes=nodes, from_nodes=from_nodes, context=context)
        except Exception as e:
            logger.exception("Experiment failed to execute with error.")
            raise e
        return experiment

    def async_start(self, executable_path=None, nodes=None, from_nodes=None, attempt=None, **kwargs):
        """Start an asynchronous execution of an experiment.

        :param executable_path: Python path when executing the experiment.
        :type executable_path: str
        :param nodes: Nodes to be executed.
        :type nodes: list
        :param from_nodes: The branches in experiment to be executed.
        :type from_nodes: list
        :param attempt: The number of attempts, it's used to records the experiment execution log.
        :type attempt: int
        :return: Experiment info.
        :rtype: ~promptflow.entities.Experiment
        """
        def _params_inject_validation(params, param_name):
            # Verify that the command is injected in the parameters.
            # parameters can only consist of numeric, alphabetic parameters, strikethrough and dash.
            pattern = r'^[a-zA-Z0-9 _\-]*$'
            for item in params:
                if not bool(re.match(pattern, item)):
                    raise ExperimentValueError(f"Invalid character found in the parameter {params} of {param_name}.")

        # Setup file handler
        file_handler, index = _set_up_experiment_log_handler(experiment_path=self.experiment._output_dir, index=attempt)
        logger.addHandler(file_handler._stream_handler)
        logger.info(f"Queuing experiment {self.experiment.name}.")
        self._update_orchestrator_record(status=ExperimentStatus.QUEUING)

        executable_path = executable_path or sys.executable
        args = [executable_path, __file__, "start", "--experiment", self.experiment.name]
        if nodes:
            _params_inject_validation(nodes, "nodes")
            args = args + ["--nodes"] + nodes
        if from_nodes:
            _params_inject_validation(from_nodes, "from-nodes")
            args = args + ["--from-nodes"] + from_nodes
        if kwargs.get("session"):
            _params_inject_validation(kwargs.get("session"), "session")
            args = args + ["--session", kwargs.get("session")]
        args = args + ["--attempt", str(index)]
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

    def _start_orchestrator(self, context, nodes=None, from_nodes=None):
        """
        Orchestrate the execution of nodes in the experiment.
        Determine node execution order through topological sorting.

        :param context: Experiment context.
        :type context: ~promptflow._sdk._orchestrator.ExperimentTemplateContext
        :param nodes: Nodes to be executed.
        :type nodes: list
        :param from_nodes: The branches in experiment to be executed.
        :type from_nodes: list
        """

        def generate_node_mapping_by_nodes(from_nodes):
            all_node_edges_mapping = {
                node.name: ExperimentHelper._prepare_single_node_edges(node) for node in self.experiment.nodes
            }
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
            logger.debug(f"Experiment nodes edges: {node_edges_mapping!r}, pre nodes: {pre_nodes!r}")
            return node_edges_mapping, pre_nodes

        def get_next_executable_nodes(completed_node=None):
            """Get the node to be executed in the experiment.

            :param completed_node: The completed node is used to update node-edge mapping in experiment run.
            :type completed_node: str
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
                pre_nodes.update(ExperimentHelper._prepare_single_node_edges(node_mapping[node_name]))
            if not check_in_degree_node_outputs(pre_nodes):
                raise UserErrorException(f"The output(s) of in-degree of nodes {nodes} do not exist.")
            node_edges_mapping = {}
            next_execute_nodes = [self._nodes[name] for name in nodes]
        else:
            # Execute all nodes in experiment.
            node_edges_mapping = {
                node.name: ExperimentHelper._prepare_single_node_edges(node) for node in self.experiment.nodes
            }
            logger.debug(f"Experiment nodes edges: {node_edges_mapping!r}")
            next_execute_nodes = get_next_executable_nodes()

        while len(next_execute_nodes) != 0 or len(future_to_node_run) != 0:
            for node in next_execute_nodes:
                # Start node execution.
                logger.info(f"Running node {node.name}.")
                exp_node_run = ExperimentNodeRun(
                    node=node,
                    context=context,
                    experiment=self.experiment,
                    node_runs=self._node_runs,
                    client=self._client,
                )
                future_to_node_run[executor.submit(exp_node_run.submit)] = exp_node_run
            completed_futures, _ = futures.wait(future_to_node_run.keys(), return_when=futures.FIRST_COMPLETED)
            next_execute_nodes = []
            for future in completed_futures:
                node_name = future_to_node_run[future].node.name
                try:
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
                    logger.exception(f"Node {future_to_node_run[future].node.name} failed to execute with error.")
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

    def __init__(self, node, experiment, context, node_runs, client, **kwargs):
        from promptflow._sdk._configuration import Configuration

        self.node = node
        self.context = context
        self.experiment = experiment
        self.experiment_data = {data.name: data for data in experiment.data}
        self.experiment_inputs = {input.name: input for input in experiment.inputs}
        self.node_runs = node_runs
        self.client = client
        self.run_operations = self.client.runs

        self.node_context = self.context.get_node_context(
            node.name, is_flow=node.type == ExperimentNodeType.FLOW, test=False
        )
        # Config run output path to experiment output folder
        run_output_path = (Path(experiment._output_dir) / "runs" / node.name).resolve().absolute().as_posix()
        super().__init__(
            # Use node name as prefix for run name?
            type=EXP_NODE_TYPE_2_RUN_TYPE[node.type],
            name=self.context.node_name_to_id[node.name],
            display_name=getattr(node, "display_name", None) or node.name,
            column_mapping=getattr(node, "inputs", None),
            variant=getattr(node, "variant", None),
            flow=self._get_node_path(),
            outputs=getattr(node, "outputs", None),
            connections=getattr(node, "connections", None),
            command=getattr(node, "command", None),
            environment_variables=getattr(node, "environment_variables", None),
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
        if self.node.type in [ExperimentNodeType.FLOW, ExperimentNodeType.COMMAND]:
            resolved_mapping = self._resolve_single_column_mapping(self.column_mapping)
        elif self.node.type == ExperimentNodeType.CHAT_GROUP:
            # for chat group node, resolve column mapping for each role
            for role in self.node.roles:
                if "inputs" in role:
                    resolved_mapping[role["role"]] = self._resolve_single_column_mapping(role["inputs"])
        logger.debug(f"Resolved node {self.node.name!r} column mapping {resolved_mapping}.")
        self.column_mapping = resolved_mapping

    def _resolve_single_column_mapping(self, column_mapping: Dict[str, Any]):
        """Resolve single column mapping with given column mapping dict"""
        if column_mapping is None:
            return None

        resolved_mapping = {}
        for name, value in column_mapping.items():
            if not isinstance(value, str) or not value.startswith("${inputs."):
                resolved_mapping[name] = value
                continue
            input_name = value.split(".")[1].replace("}", "")
            if input_name not in self.experiment_inputs:
                raise ExperimentValueError(
                    f"Input value {value!r} is specified in node {self.node.name!r}, but the related experiment input "
                    f"{input_name!r} is not found. Allowed inputs are {list(self.experiment_inputs.keys())}."
                )
            resolved_mapping[name] = self.experiment_inputs[input_name].default
        return resolved_mapping

    def _resolve_input_dirs(self):
        logger.info("Start resolve node %s input dirs.", self.node.name)
        # Get the node referenced data and run
        referenced_data, referenced_run = ExperimentHelper.get_referenced_data_and_run(
            node_name=self.node.name,
            node_type=self.node.type,
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
            return self.node.code
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
        exp_node_run_submitter = ExperimentFlowRunSubmitter(self.client)
        # e.g. attributes: {"experiment": xxx, "reference_batch_run_id": xxx}
        return exp_node_run_submitter.submit(self, session=self.context.session, attributes=self.node_context)

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
    def __init__(self, template: ExperimentTemplate, session=None, **kwargs):
        """Context for experiment template.
        :param template: Template object to get definition of experiment.
        :param session: The session id for the test trace.
        """
        self.template = template
        self._experiment_context = self._get_experiment_context()
        # Generate line run id for node
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        self.node_name_to_id = {node.name: f"{node.name}_attempt{timestamp}" for node in template.nodes}
        # context_node_name is the skip node name, overwrite input/run_id node name
        context_node_name = kwargs.get("context_node_name", None)
        # context_run_id is the respective run id of flow naming context_node_name
        context_run_id = kwargs.get("context_run_id", None)
        if context_run_id and context_node_name:
            self.node_name_to_id[context_node_name] = context_run_id
        self.node_name_to_referenced_id = self._prepare_referenced_ids()
        # All run/line run in experiment should use same session
        self.session = session or str(uuid.uuid4())

    def _prepare_referenced_ids(self):
        """Change name: [referenced_name] to name: [referenced_id]."""
        edges = ExperimentHelper.get_experiment_node_edges(self.template.nodes, flow_only=True)
        # Remove non flow node

        # Calculate root parent for each node
        node_parent = {node.name: node.name for node in self.template.nodes}

        def _find_root(node_name):
            if node_parent[node_name] != node_name:
                node_parent[node_name] = _find_root(node_parent[node_name])
            return node_parent[node_name]

        def _union(node_name1, node_name2):
            root1, root2 = _find_root(node_name1), _find_root(node_name2)
            if root1 != root2:
                node_parent[root1] = root2

        # Union node by edges, e.g. edge: eval: [main]
        for node_name, referenced_names in edges.items():
            for referenced_name in referenced_names:
                _union(node_name, referenced_name)

        result = {
            name: [self.node_name_to_id[_find_root(referenced_name)] for referenced_name in edges]
            for name, edges in edges.items()
        }
        logger.debug(f"Resolved node name to id mapping: {self.node_name_to_id}, referenced id mapping {result}.")
        return result

    def _get_experiment_context(self):
        """Get the experiment context required for trace."""
        if not self.template._source_path:
            return {}
        return {ContextAttributeKey.EXPERIMENT: Path(self.template._source_path).resolve().absolute().as_posix()}

    def get_node_context(self, node_name, is_flow, test=False):
        """Get the context for a node."""
        node_context = {**self._experiment_context}
        referenced_key = (
            ContextAttributeKey.REFERENCED_LINE_RUN_ID if test else ContextAttributeKey.REFERENCED_BATCH_RUN_ID
        )
        referenced_ids = self.node_name_to_referenced_id.get(node_name, [])
        # Add reference context only for flow node
        if is_flow:
            # Set reference line run id even if it's None to avoid stale value set by previous node
            node_context[referenced_key] = next(iter(referenced_ids)) if referenced_ids else None
        logger.debug(f"Node {node_name!r} node_context {node_context}.")
        if not test:
            # Return node context dict directly and will be set as trace attribute
            return node_context
        # Return the full json context for test
        global_context = os.environ.get(PF_TRACE_CONTEXT)
        # Expected global context: {"endpoint": "..", PF_TRACE_CONTEXT_ATTR: {..}}
        global_context = json.loads(global_context) if global_context else {"endpoint": "", PF_TRACE_CONTEXT_ATTR: {}}
        global_context[PF_TRACE_CONTEXT_ATTR].update(node_context)
        return {PF_TRACE_CONTEXT: json.dumps(global_context)}


class ExperimentTemplateTestContext(ExperimentTemplateContext):
    def __init__(
        self,
        template: ExperimentTemplate,
        override_data=None,
        override_inputs=None,
        environment_variables=None,
        output_path=None,
        session=None,
        **kwargs,
    ):
        """
        Test context for experiment template.
        :param template: Template object to get definition of experiment.
        :param override_data: User inputs when calling test command.
        :param environment_variables: Environment variables specified for test.
        :param output_path: The custom output path.
        :param session: The session id for the test trace.
        """
        super().__init__(template, session=session, **kwargs)
        override_inputs = override_inputs or {}
        self.environment_variables = environment_variables or {}
        self.node_results = {}  # E.g. {'main': {'category': 'xx', 'evidence': 'xx'}}
        self.node_inputs = {}  # E.g. {'main': {'url': 'https://abc'}}
        self.test_data = ExperimentHelper.prepare_test_data(override_data, template)
        self.test_inputs = {input.name: override_inputs.get(input.name, input.default) for input in template.inputs}
        self.command_node_names = set({node.name for node in template.nodes if node.type == ExperimentNodeType.COMMAND})
        # TODO: Update session part after test session is supported
        if output_path:
            self.output_path = Path(output_path)
        else:
            self.output_path = (
                Path(tempfile.gettempdir()) / PROMPT_FLOW_DIR_NAME / "sessions/default" / template.dir_name
            )

    def add_node_inputs(self, name, inputs):
        self.node_inputs[name] = inputs

    def add_node_result(self, name, result):
        if is_dataclass(result):
            # Convert dataclass to dict to ensure reference work
            result = result.__dict__
        supported_none_dict_types = (list, tuple, set, str, int, float, bool, type(None))
        if isinstance(result, supported_none_dict_types):
            # Convert primitive type to dict
            result = {"output": result}
        if not isinstance(result, dict):
            raise ExperimentValueError(
                f"Unsupported node {name!r} result type {type(result)}, "
                f"only dict, dataclass object and primitive type is supported."
            )
        self.node_results[name] = result


class ExperimentHelper:
    @staticmethod
    def prepare_test_data(override_data, template: ExperimentTemplate) -> dict:
        """Prepare test data.
        If override_data is given, use it for all test data.
        Else, read the first line of template data path for test."""
        template_test_data = {}
        for data in template.data:
            data_line = override_data or next(iter(load_data(local_path=data.path)), None)
            if not data_line:
                raise ExperimentValueError(f"Experiment data {data.name!r} is empty.")
            template_test_data[data.name] = data_line
        return template_test_data

    @staticmethod
    def get_referenced_data_and_run(
        node_name: str, node_type: str, column_mapping: dict, experiment_data: dict, experiment_runs: dict
    ) -> tuple:
        """Get the node referenced data and runs from dict."""
        if node_type in [ExperimentNodeType.FLOW, ExperimentNodeType.COMMAND]:
            return ExperimentHelper.get_data_and_run_from_single_column_mapping(
                node_name, column_mapping, experiment_data, experiment_runs
            )
        # for chat group node, get data and run from all roles column mapping
        elif node_type == ExperimentNodeType.CHAT_GROUP:
            data, run = {}, {}
            for role, role_column_mapping in column_mapping.items():
                role_data, role_run = ExperimentHelper.get_data_and_run_from_single_column_mapping(
                    node_name, role_column_mapping, experiment_data, experiment_runs
                )
                data.update(role_data)
                run.update(role_run)
            return data, run
        raise ExperimentValueError(f"Unknown experiment node type {node_type!r} from node {node_name!r}.")

    @staticmethod
    def get_data_and_run_from_single_column_mapping(
        node_name: str, column_mapping: dict, experiment_data: dict, experiment_runs: dict
    ):
        """Get the node referenced data and runs from dict."""
        data, run = {}, {}
        for value in column_mapping.values():
            if not isinstance(value, str) or value.startswith("${inputs."):
                continue
            # ${parent.conversation_history} is a special binding for chat group node
            if value == f"${{{CHAT_GROUP_REFERENCE_NAME}.{CONVERSATION_HISTORY}}}":
                continue
            elif value.startswith("${data."):
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
            resolved_mapping[name] = experiment_inputs[input_name]
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

        # if node is chat group, then get all inputs from roles
        node_input_values = []
        if node.type == ExperimentNodeType.CHAT_GROUP:
            for role in node.roles:
                role_inputs = role.get("inputs", {}).values()
                node_input_values.append(list(role_inputs))
        else:
            node_input_values = list(node.inputs.values())

        # Get all in-degree nodes of this node
        for input_value in node_input_values:
            if not isinstance(input_value, str):
                continue
            if ExperimentHelper._is_node_reference(input_value):
                referenced_node_name = input_value.split(".")[0].replace("${", "")
                node_names.add(referenced_node_name)
        return node_names

    @staticmethod
    def get_experiment_node_edges(nodes, flow_only=False):
        """Get experiment node edges mapping."""
        edges = {node.name: ExperimentHelper._prepare_single_node_edges(node) for node in nodes}
        if flow_only:
            nodes_to_remove = [node for node in nodes if node.type != ExperimentNodeType.FLOW]
            ExperimentHelper._remove_nodes_from_active_edges(nodes_to_remove, edges)
        return edges

    @staticmethod
    def _remove_nodes_from_active_edges(nodes_to_remove, edges):
        for node in nodes_to_remove:
            for referenced_nodes in edges.values():
                referenced_nodes.discard(node.name)
            del edges[node.name]

    @staticmethod
    def resolve_nodes_to_execute(experiment, start_nodes=None):
        """Resolve node to execute and ensure nodes order in experiment."""

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
        edges = ExperimentHelper.get_experiment_node_edges(nodes)
        active_edges = copy.deepcopy(edges)
        # If start nodes specified, preprocessing them.
        ExperimentHelper._remove_nodes_from_active_edges(start_nodes, active_edges)
        resolved_nodes.extend(start_nodes)
        logger.debug(f"Experiment start node {[node.name for node in start_nodes]}, nodes edges: {active_edges!r}")

        while True:
            available_nodes = [node for node in nodes if _can_remove_node(node)]
            logger.debug(f"Experiment available nodes: {[node.name for node in available_nodes]!r}")
            if not available_nodes:
                break
            ExperimentHelper._remove_nodes_from_active_edges(available_nodes, active_edges)
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

    def submit(self, run: ExperimentNodeRun, stream=False, **kwargs):
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

    @classmethod
    def _resolve_inputs(cls, node_name, column_mapping, input_data):
        """Resolve binding inputs to constant values."""
        # e.g. "input_path": "${data.my_data}" -> "${inputs.input_path}": "real_data_path"
        logger.info("Start resolve node %s inputs.", node_name)

        logger.debug(f"Resolved node {node_name} binding inputs {input_data}.")
        # resolve inputs
        resolved_inputs = {}
        for name, value in column_mapping.items():
            if not isinstance(value, str) or not value.startswith("${"):
                resolved_inputs[name] = value
                continue
            # my_input: "${run.outputs}" -> my_input: run_outputs_path
            input_key = value.lstrip("${").rstrip("}")
            if input_key in input_data:
                resolved_inputs[name] = input_data[input_key]
                continue
            logger.warning(
                f"Possibly invalid partial input value binding {value!r} found for node {node_name!r}. "
                "Only full binding is supported for command node. For example: ${data.my_data}, ${main_node.outputs}."
            )
            resolved_inputs[name] = value
        logger.debug(f"Resolved node {node_name} inputs {resolved_inputs}.")
        return resolved_inputs

    @classmethod
    def _resolve_outputs(cls, node_name, output_mapping, base_output_dir):
        """Resolve outputs to real path."""
        # e.g. "output_path": "${outputs.my_output}" -> "${outputs.output_path}": "real_output_path"
        logger.info("Start resolve node %s outputs.", node_name)
        # resolve outputs
        resolved_outputs = {}
        for name, value in output_mapping.items():
            # Set default output path if user doesn't set it
            if not value:
                # Create default output path if user doesn't set it
                value = base_output_dir / name
                value.mkdir(parents=True, exist_ok=True)
                value = value.resolve().absolute().as_posix()
                # Update default to run
                output_mapping[name] = value
            # Note: We will do nothing if user config the value, as we don't know it's a file or folder
            resolved_outputs[name] = value
        logger.debug(f"Resolved node {node_name} outputs {resolved_outputs}.")
        return resolved_outputs

    @classmethod
    def _resolve_command(cls, node_name, command, inputs: dict, outputs: dict):
        """Resolve command to real command."""
        logger.info("Start resolve node %s command.", node_name)
        # resolve command
        resolved_command = command
        # replace inputs
        for name, value in inputs.items():
            resolved_command = resolved_command.replace(f"${{inputs.{name}}}", str(value))
        # replace outputs
        for name, value in outputs.items():
            resolved_command = resolved_command.replace(f"${{outputs.{name}}}", str(value))
        logger.debug(f"Resolved node {node_name} command {resolved_command}.")
        if "${" in resolved_command:
            logger.warning(
                f"Possibly unresolved command value binding found for node {node_name!r}. "
                f"Resolved command: {resolved_command}. Please check your command again."
            )
        return resolved_command

    def _submit_command_run(self, run: ExperimentNodeRun, local_storage: LocalStorageOperations) -> dict:
        # resolve environment variables
        SubmitterHelper.resolve_environment_variables(environment_variables=run.environment_variables)
        SubmitterHelper.init_env(environment_variables=run.environment_variables)

        # resolve inputs & outputs for command preparing
        # e.g. input_path: ${data.my_data} -> ${inputs.input_path}: real_data_path
        inputs = self._resolve_inputs(run.node.name, run.column_mapping, run._input_data)
        outputs = self._resolve_outputs(run.node.name, run._outputs, run._output_path)

        # replace to command
        command = self._resolve_command(run.node.name, run._command, inputs, outputs)

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
        logger.info(f"Start running command {command}, log path: {log_path}")
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
    start_orchestrator_parser.add_argument("--attempt", type=str, help="The number of attempt to execute experiment.")
    start_orchestrator_parser.add_argument("--session", type=str, help="Session id of experiment execution.")
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
        ExperimentOrchestrator(client, experiment=experiment).start(
            nodes=args.nodes, from_nodes=args.from_nodes, session=args.session, attempt=args.attempt
        )
