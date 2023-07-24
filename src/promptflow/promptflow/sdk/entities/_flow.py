# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import abc
import base64
import hashlib
import json
import os
import shutil
import uuid
from os import PathLike
from pathlib import Path
from typing import Optional, Union

import pandas
import yaml
from dotenv import load_dotenv

from promptflow._cli.pf_logger_factory import _LoggerFactory
from promptflow.contracts.flow import BatchFlowRequest
from promptflow.contracts.flow import Flow as ExecutableFlow
from promptflow.contracts.flow import NodesRequest
from promptflow.contracts.run_mode import RunMode
from promptflow.data.data import load_data
from promptflow.exceptions import ErrorTarget, UserErrorException
from promptflow.utils.context_utils import inject_sys_path
from promptflow.utils.utils import reverse_transpose

from ..._constants import PROMPTFLOW_EVAL_INFO_RELATIVE_PATH
from .._constants import DAG_FILE_NAME, LOCAL_MGMT_DB_PATH
from .._utils import render_jinja_template
from .._vendor import get_ignore_file, traverse_directory
from ._bulk_flow_run import BulkFlowRun
from ._run_inputs import EvalInputs

logger = _LoggerFactory.get_logger()


class FlowBase(abc.ABC):
    @classmethod
    # pylint: disable=unused-argument
    def _resolve_cls_and_type(cls, data, params_override):
        """Resolve the class to use for deserializing the data. Return current class if no override is provided.
        :param data: Data to deserialize.
        :type data: dict
        :param params_override: Parameters to override, defaults to None
        :type params_override: typing.Optional[list]
        :return: Class to use for deserializing the data & its "type". Type will be None if no override is provided.
        :rtype: tuple[class, typing.Optional[str]]
        """
        return cls, "flow"


class Flow(FlowBase):
    def __init__(
        self,
        code: str,
        **kwargs,
    ):
        self._code = Path(code)
        path = kwargs.pop("path", None)
        self._path = Path(path) if path else None
        super().__init__(**kwargs)

    @property
    def code(self) -> Path:
        return self._code

    @code.setter
    def code(self, value: Union[str, PathLike, Path]):
        self._code = value

    @property
    def path(self) -> Path:
        flow_file = self._path or self.code / DAG_FILE_NAME
        if not flow_file.is_file():
            raise UserErrorException(
                "The directory does not contain a valid flow.",
                target=ErrorTarget.CONTROL_PLANE_SDK,
            )
        return flow_file

    @classmethod
    def load(
        cls,
        source: Union[str, PathLike],
        **kwargs,
    ):
        source_path = Path(source)
        if not source_path.exists():
            raise Exception(f"Source {source} does not exist")
        if source_path.is_dir() and (source_path / DAG_FILE_NAME).is_file():
            return cls(code=source_path.absolute().as_posix(), **kwargs)
        elif source_path.is_file() and source_path.name == DAG_FILE_NAME:
            # TODO: for file, we should read the yaml to get code and set path to source_path
            return cls(code=source_path.absolute().parent.as_posix(), **kwargs)

        raise Exception("source must be a directory or a flow.dag.yaml file")

    @classmethod
    def _init_coordinator_from_env(cls, environment_variables):
        from promptflow.executor.executor import FlowExecutionCoodinator

        # load environment variables
        # TODO: restore the original environment variables after execution
        if isinstance(environment_variables, dict):
            os.environ.update(environment_variables)
        elif isinstance(environment_variables, (str, PathLike, Path)):
            load_result = load_dotenv(environment_variables)
            if not load_result:
                path = Path(environment_variables).absolute().as_posix()
                logger.warning(f"No environment variable is set by loading {path!r}.")

        return FlowExecutionCoodinator.init_from_env()

    def _init_executable(self, tuning_node=None, variant=None) -> ExecutableFlow:
        from promptflow.sdk.operations._run_submitter import variant_overwrite_temp_flow

        with variant_overwrite_temp_flow(self.code, tuning_node, variant) as flow:
            return ExecutableFlow.from_yaml(flow_file=flow.path, working_dir=flow.code)

    def _load_inputs(self, origin_input, coordinator, *, is_eval_collection_mode=False, top=None):
        if isinstance(origin_input, EvalInputs):
            batch_inputs = self._construct_eval_batch_inputs_with_coordinator(
                origin_input, coordinator=coordinator, is_eval_collection_mode=is_eval_collection_mode
            )
        else:
            batch_inputs = load_data(origin_input)

        if not batch_inputs:
            raise UserErrorException(
                "resolve empty data from data_uri",
                target=ErrorTarget.CONTROL_PLANE_SDK,
            )

        if top:
            batch_inputs = batch_inputs[:top]
        return batch_inputs

    @classmethod
    def _get_local_connections(cls, executable: ExecutableFlow):
        from promptflow.sdk._pf_client import PFClient

        connection_names = executable.get_connection_names()
        local_client = PFClient()
        result = {}
        for n in connection_names:
            try:
                conn = local_client.connections.get(name=n, with_secrets=True)
                result[n] = conn.to_execution_connection_dict()
            except ValueError:
                # ignore when connection not found since it can be configured with env var.
                raise Exception(f"Connection {n!r} required for flow {executable.name} is not found.")
        return result

    def _run_bulk(
        self,
        executable: ExecutableFlow,
        bulk_input,
        batch_inputs,
        coordinator,
        connections=None,
        run_id=None,
        log_path=None,
    ):
        if run_id:
            batch_run_id = run_id
        else:
            batch_run_id = str(uuid.uuid4())
        connections = connections or self._get_local_connections(executable=executable)
        req = BatchFlowRequest(
            executable,
            # if executable involved a connection neither provided by connections nor by environment variable,
            # an error will be raised by executor, so no need to check here
            connections=connections,
            batch_inputs=batch_inputs,
        )
        coordinator._run_tracker._activate_in_context()
        coordinator._ensure_submission_data(req, run_mode=0)
        from ...executor.flow_request_validator import FlowRequestValidator

        FlowRequestValidator.ensure_flow_valid(req.flow, connections=connections)
        result = coordinator._exec_batch_request(
            batch_run_id,
            # TODO 2474352: what's this field? why is this a mock str?
            "mock-bulk-test-run-id",
            executable.id,
            req,
            run_id_to_log_path={batch_run_id: log_path} if log_path else None,
        )
        coordinator._run_tracker._deactivate_in_context()
        # print(f"is_evalution_flow: {self.is_evaluation_flow}")
        # print(f"result: {json.dumps(result)}")
        output = result["flow_runs"][0]["output"]
        detail = result
        metrics = result["flow_runs"][0].get("metrics", None)

        filtered_input = self._filter_and_transpose_input(batch_inputs, executable)
        if isinstance(bulk_input, EvalInputs):
            bulk_evaluation_flow_run = BulkFlowRun(
                name=batch_run_id,
                flow_id=executable.id,
                input=filtered_input,
                output=output,
                detail=detail,
                metrics=metrics,
            )

            return bulk_evaluation_flow_run
        else:
            return BulkFlowRun(
                name=batch_run_id,
                flow_id=executable.id,
                input=filtered_input,
                output=output,
                detail=detail,
            )

    def _single_run(self, request, coordinator, connections=None, run_id=None):
        coordinator._run_tracker._activate_in_context()
        coordinator._ensure_submission_data(request, run_mode=RunMode.SingleNode)
        from ...executor.flow_request_validator import FlowRequestValidator

        FlowRequestValidator.ensure_flow_valid(request.flow, connections=connections or {})
        node_run_result = coordinator._exec_nodes_request(request, RunMode.SingleNode)
        coordinator._run_tracker._deactivate_in_context()
        if not run_id:
            run_id = str(uuid.uuid4())
        return BulkFlowRun(
            flow_id=run_id,
            detail=node_run_result,
        )

    def run_bulk(
        self,
        input: Union[PathLike, EvalInputs],
        *,
        connections: dict = None,
        environment_variables: Union[dict, str, PathLike, Path] = None,
        log_path: Optional[str] = None,
    ) -> BulkFlowRun:
        """
        Run the flow in bulk mode.
        :param input: Data to run the flow on.
        :type input: Union[PathLike, EvalInputs]
        :param connections: Connections to use for the run, defaults to None.
        :type connections: dict, optional
        :param output: Output directory to save the results to, defaults to None. If None, results will be output
        to console and will not be saved to file.
        :param environment_variables: Environment variables to use for the run, defaults to None. If None, will use
        environment variables from the current environment; if a dict, will update the current environment variables
        with the provided dict; if a str or PathLike, will load the environment variables from the provided file and
        update current environment variables with them.
        :type environment_variables: Union[dict, str, PathLike, Path], optional
        :param log_path: Log path
        :type log_path: str, optional
        :return: BulkFlowRun object containing the results of the run.
        :rtype: BulkFlowRun
        """
        coordinator = self._init_coordinator_from_env(environment_variables)
        executable = self._init_executable()

        batch_inputs = self._load_inputs(input, coordinator, is_eval_collection_mode="variant_ids" in executable.inputs)
        run = self._run_bulk(
            executable=executable,
            bulk_input=input,
            batch_inputs=batch_inputs,
            coordinator=coordinator,
            connections=connections,
            log_path=log_path,
        )

        return run

    def run(
        self,
        input: Union[PathLike, EvalInputs],
        *,
        connections: dict = None,
        environment_variables: Union[dict, str, PathLike, Path] = None,
        run_id: str = None,
        log_path: str = None,
    ) -> BulkFlowRun:
        """
        Run the flow on single sample.
        :param input: Data to run the flow on. Will only use the first sample in the data.
        :type input: Union[PathLike, EvalInputs]
        :param connections: Connections to use for the run, defaults to None.
        :type connections: dict, optional
        :param environment_variables: Environment variables to use for the run, defaults to None. If None, will use
        environment variables from the current environment; if a dict, will update the current environment variables
        with the provided dict; if a str or PathLike, will load the environment variables from the provided file and
        update current environment variables with them.
        :type environment_variables: Union[dict, str, PathLike, Path], optional
        :param run_id: Run id of the flow run.
        :type run_id: str
        :param log_path: Log path of flow run.
        :type log_path: str
        :return: BulkFlowRun object containing the results of the run.
        :rtype: BulkFlowRun
        """
        coordinator = self._init_coordinator_from_env(environment_variables)
        executable = self._init_executable()

        batch_inputs = self._load_inputs(
            input, coordinator, is_eval_collection_mode="variant_ids" in executable.inputs, top=1
        )

        # TODO: should we return a FlowRun object here?
        # TODO: I haven't found where the run mode is set or even used in current local SDK
        return self._run_bulk(
            executable=executable,
            bulk_input=input,
            batch_inputs=batch_inputs,
            coordinator=coordinator,
            connections=connections,
            run_id=run_id,
            log_path=log_path,
        )

    def _single_node_run(
        self,
        node: str,
        input: Union[PathLike, EvalInputs],
        *,
        connections: dict = None,
        environment_variables: Union[dict, str, PathLike, Path] = None,
    ) -> BulkFlowRun:
        coordinator = self._init_coordinator_from_env(environment_variables)
        executable = self._init_executable()

        batch_inputs = self._load_inputs(
            input, coordinator, is_eval_collection_mode="variant_ids" in executable.inputs, top=1
        )

        request = NodesRequest(
            executable,
            connections=connections or self._get_local_connections(executable=executable),
            node_name=node,
            node_inputs=batch_inputs[0],
        )
        return self._single_run(request, coordinator, connections=connections)

    def _single_node_debug(
        self,
        node_name: str,
        input: Union[PathLike, EvalInputs],
        *,
        connections: dict = None,
        environment_variables: Union[dict, str, PathLike, Path] = None,
    ):
        from promptflow.contracts.flow import InputValueType
        from promptflow.contracts.tool import ToolType

        def get_connection_obj(connection_dict):
            from importlib import import_module

            connection_cls = getattr(import_module(connection_dict["module"]), connection_dict["type"])
            return connection_cls(**connection_dict["value"])

        executable = self._init_executable()
        coordinator = self._init_coordinator_from_env(environment_variables)
        batch_inputs = self._load_inputs(
            input, coordinator, is_eval_collection_mode="variant_ids" in executable.inputs, top=1
        )
        func_input = batch_inputs[0]

        debugging_node = next(filter(lambda item: item.name == node_name, executable.nodes), None)
        if not debugging_node:
            raise RuntimeError(f"Cannot find {node_name} in the flow.")
        if debugging_node.type != ToolType.PYTHON:
            raise RuntimeError(f"Node {node_name} with type: {debugging_node.type} is not supported for debugging.")
        debugging_tool = next(filter(lambda item: item.name == debugging_node.tool, executable.tools), None)
        if not debugging_tool:
            raise ValueError(f"Tool {debugging_node.tool} of the node {node_name} not found in flow")

        node_inputs_dict = {}
        connection_imports = ""
        for input_name, input_def in debugging_node.inputs.items():
            func_input_name = f"{input_def.prefix}{input_def.value}"
            if input_def.value_type == InputValueType.FLOW_INPUT and func_input_name in func_input:
                node_inputs_dict[input_name] = func_input[func_input_name]
            elif input_def.value_type == InputValueType.NODE_REFERENCE and func_input_name in func_input:
                node_inputs_dict[input_name] = func_input[func_input_name]
            elif input_def.value_type == InputValueType.LITERAL:
                node_inputs_dict[input_name] = input_def.value
            elif input_def.value in connections:
                connection_type = connections[input_def.value]["type"]
                node_inputs_dict[input_name] = get_connection_obj(connections[input_def.value])
                connection_imports += f"from promptflow.connections import {connection_type}\n"
            else:
                logger.warning(f"Cannot find the input {input_name}.")

        with inject_sys_path(self.code):
            exec_code = (
                connection_imports
                + f"""
from {os.path.basename(debugging_node.source.path).replace('.py', '')} import {debugging_tool.function}
{debugging_tool.function}(**{node_inputs_dict})
    """
            )

            exec(exec_code)

    def eval(
        self,
        evaluation_flow: Union["Flow", str, PathLike, Path],
        input: Union[PathLike, EvalInputs],
        *,
        column_mapping: dict,
        bulk_run_output: Union[PathLike, str],
        eval_output: Union[PathLike, str] = None,
        connections=None,
    ) -> BulkFlowRun:
        """
        Evaluate the flow run output with the evaluation flow.
        :param evaluation_flow: Evaluation flow to run.
        :type evaluation_flow: Flow
        :param input: Data to run the flow on.
        :type input: Union[PathLike, EvalInputs]
        :param bulk_run_output: Output directory of the bulk run.
        :type bulk_run_output: Union[PathLike, str]
        :param eval_output: File path to dump the result of evaluation run.
        :type eval_output: Union[PathLike, str], optional
        :param column_mapping: Column mapping to use for the evaluation run, defaults to None.
        :type column_mapping: dict, optional
        :param connections: Connections to use for both the bulk run and evaluation run, defaults to None.
        :type connections: dict, optional
        :return: BulkFlowRun object containing the results of the evaluation run.
        :rtype: BulkFlowRun
        """
        # TODO: deprecate this
        if not isinstance(evaluation_flow, Flow):
            evaluation_flow = self.load(evaluation_flow)

        # load from bulk flow run output
        if bulk_run_output is None:
            raise ValueError("bulk_run_output cannot be None")
        eval_info_file = Path(bulk_run_output).absolute() / PROMPTFLOW_EVAL_INFO_RELATIVE_PATH
        if eval_info_file.exists():
            with open(eval_info_file, "r") as f:
                eval_info = json.load(f)
        else:
            # TODO: or we should just do a bulk run here? we have all the info we need
            raise ValueError(
                f"Could not find eval info file at {eval_info_file.as_posix()}, "
                f"please call run_bulk with output of {eval_info_file.parent.as_posix()} first."
            )

        # TODO: avoid using eval_info here?
        bulk_run = BulkFlowRun(
            # from self._path
            name=eval_info["name"],
            # from self._path
            flow_id=eval_info["flow_id"],
            # fetch from self.code / ".runs" / "xxx" by default?
            # add a new parameter to specify the input?
            input=eval_info["input"],
            # output can be read from bulk_run_output
            output=eval_info["output"],
            # TODO: what is this detail for?
            detail=eval_info["detail"],
        )

        eval_flow_input = EvalInputs(input, bulk_run, inputs_mapping=column_mapping)

        # do not pass eval_output as output here as the output format is different
        eval_run = evaluation_flow.run_bulk(eval_flow_input, connections=connections, output=None)

        if eval_output is not None:
            print("=" * 10)
            print(f"Writing output to {eval_output}...")
            output = eval_run.output
            df = pandas.DataFrame(output)
            Path(eval_output).parent.mkdir(parents=True, exist_ok=True)
            df.to_json(Path(eval_output), orient="records", lines=True)

        return eval_run

    def _construct_eval_batch_inputs_with_coordinator(
        self, bulk_flow_run_input: EvalInputs, coordinator, is_eval_collection_mode: bool
    ):
        data = load_data(bulk_flow_run_input.data)

        variant_ids = []
        standard_flow_outputs = {}
        variant_ids.append("variant_0")
        standard_flow_outputs["variant_0"] = reverse_transpose(bulk_flow_run_input.batch_run.outputs)

        # TODO: Support inputs_mapping to specify different column
        updated_inputs_mapping = self._resolve_input_mapping(bulk_flow_run_input.inputs_mapping)
        batch_inputs = coordinator._construct_eval_batch_inputs(
            data,
            variant_ids,
            standard_flow_outputs,
            updated_inputs_mapping,
            collection_mode=is_eval_collection_mode,
        )

        return batch_inputs

    def _simplify_metrics(self, metrics: dict):
        updated_metrics = {}
        for k, v in metrics.items():
            if isinstance(v, list):
                updated_metrics[k] = v[0]["value"]
        return updated_metrics

    def _filter_and_transpose_input(self, batch_inputs, flow: ExecutableFlow):
        filtered_inputs = {}
        for input in batch_inputs:
            for k in flow.inputs:
                if k not in filtered_inputs:
                    filtered_inputs[k] = []
                filtered_inputs[k].append(input[k])

        return filtered_inputs

    def _resolve_input_mapping(self, inputs_mapping: dict):
        # TODO(2471803): replace with apply_inputs_mapping
        updated_inputs_mapping = {}
        for k, v in inputs_mapping.items():
            v = v.strip("${}")
            if "outputs." in v:
                updated_inputs_mapping[k] = ".".join(v.split(".")[1:])
            else:
                updated_inputs_mapping[k] = v
        return updated_inputs_mapping

    def __repr__(self):
        # TODO: add more information like file structure
        return f"Flow(path={self.code})"


class FlowProtected(Flow):
    """
    Not sure if we need this class.
    We need to hide many "protected" methods in Flow, which will be frequently referenced in other classes.
    So one way is to maintain another protected class, which can be referenced in SDK but won't be
    exposed to users.
    """

    def _build_environment_config(self):
        flow_info = yaml.safe_load(self.path.read_text())
        # standard env object:
        # environment:
        #   image: xxx
        #   conda_file: xxx
        #   python_requirements_txt: xxx
        #   setup_sh: xxx
        # TODO: deserialize dag with structured class here to avoid using so many magic strings
        env_obj = flow_info.get("environment", {})
        from promptflow import __version__

        # version 0.0.1 is the dev version of promptflow
        env_obj["sdk_version"] = __version__ if __version__ != "0.0.1" else None

        if not env_obj.get("python_requirements_txt", None) and (Path(self.code) / "requirements.txt").is_file():
            env_obj["python_requirements_txt"] = "requirements.txt"

        env_obj["conda_env_name"] = "promptflow-serve"
        if "conda_file" in env_obj:
            conda_file = Path(self.code) / env_obj["conda_file"]
            if conda_file.is_file():
                conda_obj = yaml.safe_load(conda_file.read_text())
                if "name" in conda_obj:
                    env_obj["conda_env_name"] = conda_obj["name"]

        return env_obj

    @classmethod
    def _copy_tree(cls, source: Path, target: Path, prefix: str, render_context: dict = None):
        def is_template(path: str):
            return path.endswith(".jinja2")

        for root, _, files in os.walk(source):
            # TODO: this is wired given we have only check 1 ignore file. What if there are ignore files in subfolders?
            for source_path, target_path in traverse_directory(
                root=root, files=files, source=source.as_posix(), prefix=prefix, ignore_file=get_ignore_file(source)
            ):
                (target / target_path).parent.mkdir(parents=True, exist_ok=True)
                if render_context is None or not is_template(source_path):
                    shutil.copy(source_path, target / target_path)
                else:
                    (target / target_path[: -len(".jinja2")]).write_text(
                        render_jinja_template(source_path, **render_context)
                    )

    def _migrate_connections(self, output_dir: Path, encryption_key: str):
        executable = self._init_executable()
        connections = self._get_local_connections(executable)
        for connection_name in executable.get_connection_names():
            if connection_name not in connections:
                logger.info(
                    f"Connection {connection_name} is not found in local, skip migration. "
                    f"Service call will fail before it has been manually created inside docker "
                    f"container via `pf connection create`."
                )

        # TODO: refactor this
        # Important: this operation is very dangerous and won't support multiprocess,
        # we should only enable this on cli for now
        from promptflow.sdk._orm.session import mgmt_db_rebase
        from promptflow.sdk._pf_client import PFClient
        from promptflow.sdk.entities._connection import _Connection

        with mgmt_db_rebase((output_dir / "connections.sqlite").resolve(), customized_encryption_key=encryption_key):
            local_client = PFClient()
            for connection_name, connection_execution_dict in connections.items():
                local_client.connections.create_or_update(
                    _Connection.from_execution_connection_dict(name=connection_name, data=connection_execution_dict),
                    encryption_key=encryption_key,
                )

    def _export_to_docker(self, output_dir: Path, migration_secret: str):
        environment_config = self._build_environment_config()

        # TODO: make below strings constants
        self._copy_tree(
            source=Path(__file__).parent.parent / "data" / "docker",
            target=output_dir,
            prefix="",
            render_context={
                "env": environment_config,
                "local_db_rel_path": LOCAL_MGMT_DB_PATH.relative_to(Path.home()).as_posix(),
            },
        )

        self._copy_tree(self.code, output_dir, prefix="flow/")
        self._migrate_connections(
            output_dir,
            encryption_key=base64.urlsafe_b64encode(hashlib.sha256(migration_secret.encode("utf-8")).digest()).decode(
                "utf-8"
            ),
        )

    def export(self, output: Union[str, PathLike], migration_secret: str, format="docker"):
        output = Path(output)
        output.mkdir(parents=True, exist_ok=True)
        if format == "docker":
            self._export_to_docker(output, migration_secret)
        else:
            raise ValueError(f"Unsupported export format: {format}")
