# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# this file is a middle layer between the local SDK and executor, it'll have some similar logic with cloud PFS.

import contextlib
import hashlib
import json
import os
import platform
import re
import subprocess
import tempfile
import time
from collections import defaultdict
from os import PathLike
from pathlib import Path
from time import sleep
from types import GeneratorType
from typing import Any, Dict, List, Union

import psutil
import pydash
from dotenv import load_dotenv
from pydash import objects

from promptflow._constants import STREAMING_ANIMATION_TIME
from promptflow._proxy import ProxyFactory
from promptflow._sdk._constants import (
    ALL_CONNECTION_TYPES,
    DEFAULT_VAR_ID,
    INPUTS,
    NODE,
    NODE_VARIANTS,
    NODES,
    SUPPORTED_CONNECTION_FIELDS,
    USE_VARIANTS,
    VARIANTS,
    ConnectionFields,
)
from promptflow._sdk._errors import InvalidFlowError, RunOperationError
from promptflow._sdk._load_functions import load_flow
from promptflow._sdk._utilities.general_utils import _merge_local_code_and_additional_includes
from promptflow._sdk._utilities.signature_utils import update_signatures
from promptflow._sdk.entities._flows import FlexFlow, Flow, Prompty
from promptflow._utils.flow_utils import (
    dump_flow_dag_according_to_content,
    dump_flow_yaml_to_existing_path,
    load_flow_dag,
)
from promptflow._utils.logger_utils import FileHandler, get_cli_sdk_logger
from promptflow.contracts.flow import Flow as ExecutableFlow
from promptflow.core._utils import get_used_connection_names_from_dict, update_dict_value_with_connections
from promptflow.exceptions import UserErrorException
from promptflow.tracing.contracts.iterator_proxy import IteratorProxy

logger = get_cli_sdk_logger()


def overwrite_variant(flow_dag: dict, tuning_node: str = None, variant: str = None, drop_node_variants: bool = False):
    # need to overwrite default variant if tuning node and variant not specified.
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
        raise InvalidFlowError("Failed to overwrite tuning node with variant") from e


def overwrite_connections(flow_dag: dict, connections: dict, working_dir: PathLike):
    if not connections:
        return

    if not isinstance(connections, dict):
        raise InvalidFlowError(f"Invalid connections overwrite format: {connections}, only list is supported.")

    # Load executable flow to check if connection is LLM connection
    executable_flow = ExecutableFlow._from_dict(flow_data=flow_dag, working_dir=Path(working_dir))

    # generate tool meta for deployment name, model override
    # tools_meta = generate_flow_tools_json(flow_directory=working_dir, dump=False, used_packages_only=True)

    node_name_2_node = {node["name"]: node for node in flow_dag[NODES]}

    for node_name, connection_dict in connections.items():
        if node_name not in node_name_2_node:
            raise InvalidFlowError(f"Node {node_name} not found in flow")
        if not isinstance(connection_dict, dict):
            raise InvalidFlowError(f"Invalid connection overwrite format: {connection_dict}, only dict is supported.")
        node = node_name_2_node[node_name]
        executable_node = executable_flow.get_node(node_name=node_name)

        # override connections
        if executable_flow.is_llm_node(executable_node):
            override_llm_connections(
                node=node,
                connection_dict=connection_dict,
                node_name=node_name,
            )
        else:
            override_python_connections(
                node=node,
                connection_dict=connection_dict,
                tools_meta={},
                executable_flow=executable_flow,
                node_name=node_name,
            )


def override_llm_connections(node: dict, connection_dict: dict, node_name: str):
    """apply connection override on llm node."""
    try:
        # override connection
        connection = connection_dict.get(ConnectionFields.CONNECTION.value)
        if connection:
            logger.debug(f"Overwriting connection for node {node_name} with {connection}")
            node[ConnectionFields.CONNECTION] = connection
            connection_dict.pop(ConnectionFields.CONNECTION.value)
        # override deployment_name and model
        for field in [ConnectionFields.DEPLOYMENT_NAME.value, ConnectionFields.MODEL.value]:
            if field in connection_dict:
                logger.debug(f"Overwriting {field} for node {node_name} with {connection_dict[field]}")
                node[INPUTS][field] = connection_dict[field]
                connection_dict.pop(field)
    except KeyError as e:
        raise InvalidFlowError(f"Failed to overwrite llm node {node_name} with connections {connection_dict}") from e
    if connection_dict:
        raise InvalidFlowError(
            f"Unsupported llm connection overwrite keys: {connection_dict.keys()},"
            f" only {SUPPORTED_CONNECTION_FIELDS} are supported."
        )


def override_python_connections(
    node: dict, connection_dict: dict, tools_meta: dict, executable_flow: ExecutableFlow, node_name: str
):
    """apply connection override on python node."""
    connection_inputs = executable_flow.get_connection_input_names_for_node(node_name=node_name)
    consumed_connections = set()
    for c, v in connection_dict.items():
        if c in connection_inputs:
            logger.debug(f"Overwriting connection for node {node_name} with {c}:{v}")
            node[INPUTS][c] = v
            consumed_connections.add(c)
        else:
            # TODO(3021931): check if input c is enabled by connection instead of hard code
            logger.debug(f"Overwriting enabled by connection input for node {node_name} with {c}:{v}")
            for field in [ConnectionFields.DEPLOYMENT_NAME.value, ConnectionFields.MODEL.value]:
                if field in connection_dict:
                    logger.debug(f"Overwriting {field} for node {node_name} with {connection_dict[field]}")
                    node[INPUTS][field] = connection_dict[field]
                    consumed_connections.add(field)
    unused_connections = connection_dict.keys() - consumed_connections
    if unused_connections:
        raise InvalidFlowError(
            f"Unsupported llm connection overwrite keys: {unused_connections},"
            f" only {SUPPORTED_CONNECTION_FIELDS} are supported."
        )


def overwrite_flow(flow_dag: dict, params_overrides: dict):
    if not params_overrides:
        return

    # update flow dag & change nodes list to name: obj dict
    flow_dag[NODES] = {node["name"]: node for node in flow_dag[NODES]}
    # apply overrides on flow dag
    for param, val in params_overrides.items():
        objects.set_(flow_dag, param, val)
    # revert nodes to list
    flow_dag[NODES] = list(flow_dag[NODES].values())


def remove_additional_includes(flow_path: Path):
    flow_path, flow_dag = load_flow_dag(flow_path=flow_path)
    flow_dag.pop("additional_includes", None)
    dump_flow_yaml_to_existing_path(flow_dag, flow_path)


def override_flow_yaml(
    flow: Flow,
    flow_dag: dict,
    flow_dir_path: Path,
    tuning_node: str = None,
    variant: str = None,
    connections: dict = None,
    *,
    overrides: dict = None,
    drop_node_variants: bool = False,
    init_kwargs: dict = None,
):
    # generate meta before updating signatures since update signatures requires it.
    if not isinstance(flow, Prompty):
        ProxyFactory().create_inspector_proxy(flow.language).prepare_metadata(
            flow_file=Path(flow.path), working_dir=Path(flow.code), init_kwargs=init_kwargs
        )
    if isinstance(flow, FlexFlow):
        # update signatures for flex flow
        # no variant overwrite for eager flow
        for param in [tuning_node, variant, connections, overrides]:
            if param:
                logger.warning(
                    "Eager flow does not support tuning node, variant, connection override. " f"Dropping params {param}"
                )
        update_signatures(code=flow_dir_path, data=flow_dag)
    else:
        # always overwrite variant since we need to overwrite default variant if not specified.
        overwrite_variant(flow_dag, tuning_node, variant, drop_node_variants=drop_node_variants)
        overwrite_connections(flow_dag, connections, working_dir=flow_dir_path)
        overwrite_flow(flow_dag, overrides)


@contextlib.contextmanager
def flow_overwrite_context(
    flow: Flow,
    tuning_node: str = None,
    variant: str = None,
    connections: dict = None,
    *,
    overrides: dict = None,
    drop_node_variants: bool = False,
    init_kwargs: dict = None,
):
    """Override variant and connections in the flow."""
    flow_dag = flow._data
    flow_dir_path = Path(flow.code)
    if isinstance(flow, Prompty):
        # prompty don't support override
        yield flow
    elif getattr(flow, "additional_includes", []):
        # Merge the flow folder and additional includes to temp folder for both eager flow & dag flow.
        with _merge_local_code_and_additional_includes(code_path=flow_dir_path) as temp_dir:
            override_flow_yaml(
                flow=flow,
                flow_dag=flow_dag,
                flow_dir_path=flow_dir_path,
                tuning_node=tuning_node,
                variant=variant,
                connections=connections,
                overrides=overrides,
                drop_node_variants=drop_node_variants,
                init_kwargs=init_kwargs,
            )
            flow_dag.pop("additional_includes", None)
            dump_flow_dag_according_to_content(flow_dag=flow_dag, flow_path=Path(temp_dir))
            flow = load_flow(temp_dir)
            yield flow
    else:
        # Generate a flow, the code path points to the original flow folder,
        # the dag path points to the temp dag file after overwriting variant.
        with tempfile.TemporaryDirectory() as temp_dir:
            override_flow_yaml(
                flow=flow,
                flow_dag=flow_dag,
                flow_dir_path=flow_dir_path,
                tuning_node=tuning_node,
                variant=variant,
                connections=connections,
                overrides=overrides,
                drop_node_variants=drop_node_variants,
                init_kwargs=init_kwargs,
            )
            flow_path = dump_flow_dag_according_to_content(flow_dag=flow_dag, flow_path=Path(temp_dir))
            if isinstance(flow, FlexFlow):
                flow = FlexFlow(code=flow_dir_path, path=flow_path, data=flow_dag, entry=flow.entry)
                yield flow
            else:
                flow = Flow(code=flow_dir_path, path=flow_path, dag=flow_dag)
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
    def resolve_connections(
        flow: Flow,
        client=None,
        *,
        connections_to_ignore=None,
        connections_to_add: List[str] = None,
        environment_variables_overrides: Dict[str, str] = None,
    ) -> dict:
        from .._pf_client import PFClient

        client = client or PFClient()

        if isinstance(flow, Prompty):
            return {}

        connection_names = (
            ProxyFactory()
            .create_inspector_proxy(flow.language)
            .get_used_connection_names(
                flow_file=flow.path,
                working_dir=flow.code,
                environment_variables_overrides=environment_variables_overrides,
            )
        )

        return SubmitterHelper.resolve_connection_names(
            connection_names=connection_names,
            client=client,
            connections_to_ignore=connections_to_ignore,
            raise_error=True,
            connections_to_add=connections_to_add,
        )

    @staticmethod
    def get_used_connection_names(tools_meta: dict, flow_dag: dict):
        # TODO: handle code tool meta for python
        connection_inputs = defaultdict(set)
        for package_id, package_meta in tools_meta.get("package", {}).items():
            for tool_input_key, tool_input_meta in package_meta.get("inputs", {}).items():
                if ALL_CONNECTION_TYPES.intersection(set(tool_input_meta.get("type"))):
                    connection_inputs[package_id].add(tool_input_key)

        connection_names = set()
        # TODO: we assume that all variants are resolved here
        # TODO: only literal connection inputs are supported
        # TODO: check whether we should put this logic in executor as seems it's not possible to avoid touching
        #  information for executable
        for node in flow_dag.get("nodes", []):
            package_id = pydash.get(node, "source.tool")
            if package_id in connection_inputs:
                for connection_input in connection_inputs[package_id]:
                    connection_name = pydash.get(node, f"inputs.{connection_input}")
                    if connection_name and not re.match(r"\${.*}", connection_name):
                        connection_names.add(connection_name)
        return list(connection_names)

    @classmethod
    def load_and_resolve_environment_variables(cls, flow: Flow, environment_variable_overrides: dict, client=None):
        environment_variable_overrides = ExecutableFlow.load_env_variables(
            flow_file=flow.path, working_dir=flow.code, environment_variables_overrides=environment_variable_overrides
        )
        cls.resolve_environment_variables(environment_variable_overrides, client)
        return environment_variable_overrides

    @classmethod
    def resolve_environment_variables(cls, environment_variables: dict, client=None):
        from .._pf_client import PFClient

        client = client or PFClient()
        if not environment_variables:
            return None
        connection_names = get_used_connection_names_from_dict(environment_variables)
        logger.debug("Used connection names: %s", connection_names)
        connections = cls.resolve_connection_names(connection_names=connection_names, client=client)
        update_dict_value_with_connections(built_connections=connections, connection_dict=environment_variables)

    @staticmethod
    def resolve_connection_names(
        connection_names,
        client,
        *,
        raise_error=False,
        connections_to_ignore=None,
        connections_to_add=None,
    ):
        connection_names = set(connection_names)
        if connections_to_add:
            connection_names.update(connections_to_add)
        result = {}
        for n in connection_names:
            if connections_to_ignore and n in connections_to_ignore:
                continue
            try:
                conn = client.connections.get(name=n, with_secrets=True)
                result[n] = conn._to_execution_connection_dict()
            except Exception as e:
                if raise_error:
                    raise e
        return result


def show_node_log_and_output(node_run_infos, show_node_output, generator_record):
    """Show stdout and output of nodes."""
    from colorama import Fore

    for node_name, node_result in node_run_infos.items():
        # Prefix of node stdout is "%Y-%m-%dT%H:%M:%S%z"
        pattern = r"\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+\d{4}\] "
        if node_result.logs:
            node_logs = re.sub(pattern, "", node_result.logs["stdout"])
            if node_logs:
                for log in node_logs.rstrip("\n").split("\n"):
                    print(f"{Fore.LIGHTBLUE_EX}[{node_name}]:", end=" ")
                    print(log)
        if show_node_output:
            print(f"{Fore.CYAN}{node_name}: ", end="")
            # TODO executor return a type string of generator
            node_output = node_result.output
            if isinstance(node_result.output, GeneratorType):
                node_output = _safe_join(
                    resolve_generator_output_with_cache(
                        node_output, generator_record, generator_key=f"nodes.{node_name}.output"
                    )
                )
            print(f"{Fore.LIGHTWHITE_EX}{node_output}")


def print_chat_output(output, generator_record, *, generator_key: str):
    if isinstance(output, (IteratorProxy, GeneratorType)):
        for event in resolve_generator_output_with_cache(output, generator_record, generator_key=generator_key):
            print(event, end="")
            # For better animation effects
            time.sleep(STREAMING_ANIMATION_TIME)
        # Print a new line at the end of the response
        print()
    else:
        print(output)


def resolve_generator_output_with_cache(
    output: Union[GeneratorType, IteratorProxy], generator_record: Dict[str, Any], *, generator_key: str
) -> List[str]:
    """Get the output of a generator. If the generator has been recorded, return the recorded result. Otherwise, record
    the result and return it.
    We use a separate generator_key instead of the output itself as the key in the generator_record in case the output
    is not a valid dict key in some cases.

    :param output: The generator to get the output from.
    :type output: Union[GeneratorType, IteratorProxy]
    :param generator_record: The record of the generator.
    :type generator_record: dict
    :param generator_key: The key of the generator in the record, need to be unique.
    :type generator_key: str
    :return: The output of the generator.
    :rtype: str
    """
    if isinstance(output, (GeneratorType, IteratorProxy)):
        if generator_key in generator_record:
            if hasattr(generator_record[generator_key], "items"):
                output = iter(generator_record[generator_key].items)
            else:
                output = iter(generator_record[generator_key])
        else:
            generator_record[generator_key] = list(output)
            output = generator_record[generator_key]
    return output


def _safe_join(generator_output):
    items = []
    for item in generator_output:
        if isinstance(item, str):
            items.append(item)
        else:
            try:
                items.append(str(item))
            except Exception as e:
                raise UserErrorException(
                    message=f"Failed to convert generator output to string: {e}",
                )
    return "".join(items)


def resolve_generator(flow_result, generator_record):
    # resolve generator in flow result
    for k, v in flow_result.run_info.output.items():
        if isinstance(v, GeneratorType):
            flow_output = _safe_join(
                resolve_generator_output_with_cache(v, generator_record, generator_key=f"run.outputs.{k}")
            )
            flow_result.run_info.output[k] = flow_output
            flow_result.run_info.result[k] = flow_output
            if isinstance(flow_result.output, dict):
                flow_result.output[k] = flow_output
            else:
                flow_result.output = flow_output

    # resolve generator in node outputs
    for node_name, node in flow_result.node_run_infos.items():
        if isinstance(node.output, GeneratorType):
            node_output = _safe_join(
                resolve_generator_output_with_cache(
                    node.output, generator_record, generator_key=f"nodes.{node_name}.output"
                )
            )
            node.output = node_output
            node.result = node_output

    return flow_result


# region start experiment utils
def _start_process_in_background(args, executable_path=None):
    if platform.system() == "Windows":
        os.spawnve(os.P_DETACH, executable_path, args, os.environ)
    else:
        subprocess.Popen(" ".join(["nohup"] + args + ["&"]), shell=True, env=os.environ)


def _windows_stop_handler(experiment_name, post_process):
    import win32pipe

    # Create a named pipe to receive the cancel signal.
    pipe_name = r"\\.\pipe\{}".format(experiment_name)
    pipe = win32pipe.CreateNamedPipe(
        pipe_name,
        win32pipe.PIPE_ACCESS_DUPLEX,
        win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_WAIT,
        1,
        65536,
        65536,
        0,
        None,
    )
    # Wait for connection to stop orchestrator
    win32pipe.ConnectNamedPipe(pipe, None)
    post_process()


def _calculate_snapshot(column_mapping, input_data, flow_path):
    def calculate_files_content_hash(file_path):
        file_content = {}
        if not isinstance(file_path, (str, PathLike)) or not Path(file_path).exists():
            return file_path
        if Path(file_path).is_file():
            with open(file_path, "r") as f:
                absolute_path = Path(file_path).absolute().as_posix()
                file_content[absolute_path] = hashlib.md5(f.read().encode("utf8")).hexdigest()
        else:
            for root, dirs, files in os.walk(file_path):
                for ignore_item in ["__pycache__"]:
                    if ignore_item in dirs:
                        dirs.remove(ignore_item)
                for file in files:
                    with open(os.path.join(root, file), "r", encoding="utf-8") as f:
                        relative_path = (Path(root) / file).relative_to(Path(file_path)).as_posix()
                        try:
                            file_content[relative_path] = hashlib.md5(f.read().encode("utf8")).hexdigest()
                        except Exception as e:
                            raise e
        return hashlib.md5(json.dumps(file_content, sort_keys=True).encode("utf-8")).hexdigest()

    snapshot_content = {
        "column_mapping": column_mapping,
        "inputs": {key: calculate_files_content_hash(value) for key, value in input_data.items()},
        "code": calculate_files_content_hash(flow_path),
    }
    return hashlib.md5(json.dumps(snapshot_content, sort_keys=True).encode("utf-8")).hexdigest()


def _stop_orchestrator_process(orchestrator):
    try:
        if platform.system() == "Windows":
            import win32file

            # Connect to named pipe to stop the orchestrator process.
            win32file.CreateFile(
                r"\\.\pipe\{}".format(orchestrator.experiment_name),
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,
                None,
                win32file.OPEN_EXISTING,
                0,
                None,
            )
        else:
            # Send terminate signal to orchestrator process.
            process = psutil.Process(orchestrator.pid)
            process.terminate()
    except psutil.NoSuchProcess:
        logger.debug("Experiment orchestrator process terminates abnormally.")
        return

    except Exception as e:
        raise RunOperationError(
            message=f"Experiment stopped failed with {e}",
        )
    # Wait for status updated
    try:
        while True:
            psutil.Process(orchestrator.pid)
            sleep(1)
    except psutil.NoSuchProcess:
        logger.debug("Experiment status has been updated.")


def _set_up_experiment_log_handler(experiment_path, index=None):
    """
    Set up file handler to record experiment execution. If not set index, it will record logs in a new file.

    :param experiment_path: Experiment path.
    :type experiment_path: str
    :param index: The number of attempt to execution experiment.
    :type index: int
    :return: File handler, the number of attempt to execution experiment.
    :rtype: ~promptflow.utils.logger_utils.FileHandler, int
    """
    log_folder = Path(experiment_path) / "logs"
    log_folder.mkdir(exist_ok=True, parents=True)
    if index is None:
        # Get max index in logs folder
        index = 0
        for filename in os.listdir(log_folder):
            result = re.match(r"exp\.attempt\_(\d+)\.log", filename)
            if result:
                try:
                    index = max(index, int(result.groups()[0]) + 1)
                except Exception as e:
                    logger.debug(f"Get index of log file failed: {e}")

    log_path = Path(experiment_path) / "logs" / f"exp.attempt_{index}.log"
    logger.info(f"Experiment execution log records in {log_path}")
    file_handler = FileHandler(file_path=log_path)
    return file_handler, index


# endregion
