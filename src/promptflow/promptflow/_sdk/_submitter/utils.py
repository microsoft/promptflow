# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# this file is a middle layer between the local SDK and executor, it'll have some similar logic with cloud PFS.

import contextlib
import os
import re
import tempfile
import time
from collections import defaultdict
from os import PathLike
from pathlib import Path
from types import GeneratorType

import pydash
from dotenv import load_dotenv
from pydash import objects

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
from promptflow._sdk._errors import InvalidFlowError
from promptflow._sdk._load_functions import load_flow
from promptflow._sdk._utils import (
    _get_additional_includes,
    _merge_local_code_and_additional_includes,
    get_local_connections_from_executable,
    get_used_connection_names_from_dict,
    update_dict_value_with_connections,
)
from promptflow._sdk.entities._flow import Flow, ProtectedFlow
from promptflow._utils.context_utils import _change_working_dir
from promptflow._utils.flow_utils import dump_flow_dag, load_flow_dag
from promptflow.contracts.flow import Flow as ExecutableFlow


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
    executable_flow = ExecutableFlow._from_dict(flow_dag=flow_dag, working_dir=Path(working_dir))

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
                raise InvalidFlowError(
                    f"Failed to overwrite llm node {node_name} with connections {connections}"
                ) from e
        else:
            connection_inputs = executable_flow.get_connection_input_names_for_node(node_name=node_name)
            for c, v in connection_dict.items():
                if c not in connection_inputs:
                    raise InvalidFlowError(f"Connection with name {c} not found in node {node_name}'s inputs")
                node[INPUTS][c] = v


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
    dump_flow_dag(flow_dag, flow_path)


@contextlib.contextmanager
def variant_overwrite_context(
    flow_path: Path,
    tuning_node: str = None,
    variant: str = None,
    connections: dict = None,
    *,
    overrides: dict = None,
    drop_node_variants: bool = False,
):
    """Override variant and connections in the flow."""
    flow_dag_path, flow_dag = load_flow_dag(flow_path)
    flow_dir_path = flow_dag_path.parent
    if _get_additional_includes(flow_dag_path):
        # Merge the flow folder and additional includes to temp folder.
        with _merge_local_code_and_additional_includes(code_path=flow_path) as temp_dir:
            # always overwrite variant since we need to overwrite default variant if not specified.
            overwrite_variant(flow_dag, tuning_node, variant, drop_node_variants=drop_node_variants)
            overwrite_connections(flow_dag, connections, working_dir=flow_dir_path)
            overwrite_flow(flow_dag, overrides)
            flow_dag.pop("additional_includes", None)
            dump_flow_dag(flow_dag, Path(temp_dir))
            flow = load_flow(temp_dir)
            yield flow
    else:
        # Generate a flow, the code path points to the original flow folder,
        # the dag path points to the temp dag file after overwriting variant.
        with tempfile.TemporaryDirectory() as temp_dir:
            overwrite_variant(flow_dag, tuning_node, variant, drop_node_variants=drop_node_variants)
            overwrite_connections(flow_dag, connections, working_dir=flow_dir_path)
            overwrite_flow(flow_dag, overrides)
            flow_path = dump_flow_dag(flow_dag, Path(temp_dir))
            flow = ProtectedFlow(code=flow_dir_path, path=flow_path, dag=flow_dag)
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
    def resolve_connections(flow: Flow, client=None, connections_to_ignore=None) -> dict:
        # TODO 2856400: use resolve_used_connections instead of this function to avoid using executable in control-plane
        from promptflow._sdk.entities._eager_flow import EagerFlow

        from .._pf_client import PFClient

        if isinstance(flow, EagerFlow):
            # TODO(2898247): support prompt flow management connection for eager flow
            return {}

        client = client or PFClient()
        with _change_working_dir(flow.code):
            executable = ExecutableFlow.from_yaml(flow_file=flow.path, working_dir=flow.code)
        executable.name = str(Path(flow.code).stem)

        return get_local_connections_from_executable(
            executable=executable, client=client, connections_to_ignore=connections_to_ignore
        )

    @staticmethod
    def resolve_used_connections(flow: ProtectedFlow, tools_meta: dict, client, connections_to_ignore=None) -> dict:
        from .._pf_client import PFClient

        client = client or PFClient()
        connection_names = SubmitterHelper.get_used_connection_names(tools_meta=tools_meta, flow_dag=flow.dag)
        connections_to_ignore = connections_to_ignore or []
        result = {}
        for n in connection_names:
            if n not in connections_to_ignore:
                conn = client.connections.get(name=n, with_secrets=True)
                result[n] = conn._to_execution_connection_dict()
        return result

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
    def load_and_resolve_environment_variables(cls, flow: Flow, environment_variables: dict, client=None):
        environment_variables = ExecutableFlow.load_env_variables(
            flow_file=flow.path, working_dir=flow.code, environment_variables_overrides=environment_variables
        )
        cls.resolve_environment_variables(environment_variables, client)
        return environment_variables

    @classmethod
    def resolve_environment_variables(cls, environment_variables: dict, client=None):
        from .._pf_client import PFClient

        client = client or PFClient()
        if not environment_variables:
            return None
        connection_names = get_used_connection_names_from_dict(environment_variables)
        connections = cls.resolve_connection_names(connection_names=connection_names, client=client)
        update_dict_value_with_connections(built_connections=connections, connection_dict=environment_variables)

    @staticmethod
    def resolve_connection_names(connection_names, client, raise_error=False):
        result = {}
        for n in connection_names:
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
                node_output = "".join(get_result_output(node_output, generator_record))
            print(f"{Fore.LIGHTWHITE_EX}{node_output}")


def print_chat_output(output, generator_record):
    if isinstance(output, GeneratorType):
        for event in get_result_output(output, generator_record):
            print(event, end="")
            # For better animation effects
            time.sleep(0.01)
        # Print a new line at the end of the response
        print()
    else:
        print(output)


def get_result_output(output, generator_record):
    if isinstance(output, GeneratorType):
        if output in generator_record:
            if hasattr(generator_record[output], "items"):
                output = iter(generator_record[output].items)
            else:
                output = iter(generator_record[output])
        else:
            if hasattr(output.gi_frame.f_locals, "proxy"):
                proxy = output.gi_frame.f_locals["proxy"]
                generator_record[output] = proxy
            else:
                generator_record[output] = list(output)
                output = generator_record[output]
    return output


def resolve_generator(flow_result, generator_record):
    # resolve generator in flow result
    for k, v in flow_result.run_info.output.items():
        if isinstance(v, GeneratorType):
            flow_output = "".join(get_result_output(v, generator_record))
            flow_result.run_info.output[k] = flow_output
            flow_result.run_info.result[k] = flow_output
            flow_result.output[k] = flow_output

    # resolve generator in node outputs
    for node_name, node in flow_result.node_run_infos.items():
        if isinstance(node.output, GeneratorType):
            node_output = "".join(get_result_output(node.output, generator_record))
            node.output = node_output
            node.result = node_output

    return flow_result
