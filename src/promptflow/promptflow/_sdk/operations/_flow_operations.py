# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
from os import PathLike
from pathlib import Path
from typing import List, Union

import yaml

from promptflow._sdk._constants import CHAT_HISTORY, DAG_FILE_NAME, LOCAL_MGMT_DB_PATH
from promptflow._sdk._utils import (
    copy_tree_respect_template_and_ignore_file,
    dump_yaml,
    generate_random_string,
    parse_variant,
)
from promptflow._sdk.operations._run_submitter import variant_overwrite_context
from promptflow._sdk.operations._test_submitter import TestSubmitter
from promptflow.exceptions import UserErrorException


class FlowOperations:
    """FlowOperations."""

    def __init__(self):
        pass

    def test(
        self,
        flow: Union[str, PathLike],
        *,
        inputs: dict = None,
        variant: str = None,
        node: str = None,
        environment_variables: dict = None,
    ) -> dict:
        """Test flow or node

        :param flow: path to flow directory to test
        :type flow: Union[str, PathLike]
        :param inputs: Input data for the flow test
        :type inputs: dict
        :param variant: Node & variant name in format of ${node_name.variant_name}, will use default variant
           if not specified.
        :type variant: str
        :param node: If specified it will only test this node, else it will test the flow.
        :type node: str
        :param environment_variables: Environment variables to set by specifying a property path and value.
           Example: {"key1": "${my_connection.api_key}", "key2"="value2"}
           The value reference to connection keys will be resolved to the actual value,
           and all environment variables specified will be set into os.environ.
        :type environment_variables: dict
        :return: The result of flow or node
        :rtype: dict
        """
        result = self._test(
            flow=flow, inputs=inputs, variant=variant, node=node, environment_variables=environment_variables
        )
        TestSubmitter._raise_error_when_test_failed(result, show_trace=node is not None)
        return result.output

    def _test(
        self,
        flow: Union[str, PathLike],
        *,
        inputs: dict = None,
        variant: str = None,
        node: str = None,
        environment_variables: dict = None,
        stream_log: bool = True,
        allow_generator_output: bool = True,
    ):
        """Test flow or node

        :param flow: path to flow directory to test
        :param inputs: Input data for the flow test
        :param variant: Node & variant name in format of ${node_name.variant_name}, will use default variant
           if not specified.
        :param node: If specified it will only test this node, else it will test the flow.
        :param environment_variables: Environment variables to set by specifying a property path and value.
           Example: {"key1": "${my_connection.api_key}", "key2"="value2"}
           The value reference to connection keys will be resolved to the actual value,
           and all environment variables specified will be set into os.environ.
        : param allow_generator_output: Whether return streaming output when flow has streaming output.
        :return: Executor result
        """
        from promptflow._sdk._load_functions import load_flow

        inputs = inputs or {}
        flow = load_flow(flow)
        with TestSubmitter(flow=flow, variant=variant).init() as submitter:
            is_chat_flow, _ = self._is_chat_flow(submitter.dataplane_flow)
            if is_chat_flow and not inputs.get(CHAT_HISTORY, None):
                inputs[CHAT_HISTORY] = []
            flow_inputs, dependency_nodes_outputs = submitter._resolve_data(node_name=node, inputs=inputs)

            if node:
                return submitter.node_test(
                    node_name=node,
                    flow_inputs=flow_inputs,
                    dependency_nodes_outputs=dependency_nodes_outputs,
                    environment_variables=environment_variables,
                    stream=True,
                )
            else:
                return submitter.flow_test(
                    inputs=flow_inputs,
                    environment_variables=environment_variables,
                    stream_log=stream_log,
                    allow_generator_output=allow_generator_output,
                )

    @staticmethod
    def _is_chat_flow(flow):
        """
        Check if the flow is chat flow.
        Check if chat_history in the flow input and only one chat input and
        one chat output to determine if it is a chat flow.
        """
        chat_inputs = [item for item in flow.inputs.values() if item.is_chat_input]
        chat_outputs = [item for item in flow.outputs.values() if item.is_chat_output]
        is_chat_flow, error_msg = True, ""
        if len(chat_inputs) != 1:
            is_chat_flow = False
            error_msg = "chat flow does not support multiple chat inputs"
        elif len(chat_outputs) != 1:
            is_chat_flow = False
            error_msg = "chat flow does not support multiple chat outputs"
        elif CHAT_HISTORY not in flow.inputs:
            is_chat_flow = False
            error_msg = "chat_history is required in the inputs of chat flow"
        return is_chat_flow, error_msg

    def _chat(
        self,
        flow,
        *,
        inputs: dict = None,
        variant: str = None,
        environment_variables: dict = None,
        **kwargs,
    ) -> List:
        """Interact with Chat Flow. Only chat flow supported.

        :param flow: path to flow directory to chat
        :param inputs: Input data for the flow to chat
        :param environment_variables: Environment variables to set by specifying a property path and value.
           Example: {"key1": "${my_connection.api_key}", "key2"="value2"}
           The value reference to connection keys will be resolved to the actual value,
           and all environment variables specified will be set into os.environ.
        """
        from promptflow._sdk._load_functions import load_flow

        flow = load_flow(flow)
        with TestSubmitter(flow=flow, variant=variant).init() as submitter:
            is_chat_flow, error_msg = self._is_chat_flow(submitter.dataplane_flow)
            if not is_chat_flow:
                raise UserErrorException(f"Only support chat flow in interactive mode, {error_msg}.")

            info_msg = f"Welcome to chat flow, {submitter.dataplane_flow.name}."
            print("=" * len(info_msg))
            print(info_msg)
            print("Press Enter to send your message.")
            print("You can quit with ctrl+Z.")
            print("=" * len(info_msg))
            submitter._chat_flow(
                inputs=inputs,
                environment_variables=environment_variables,
                show_step_output=kwargs.get("show_step_output", False),
            )

    @classmethod
    def _build_environment_config(cls, flow_dag_path: Path):
        flow_info = yaml.safe_load(flow_dag_path.read_text())
        # standard env object:
        # environment:
        #   image: xxx
        #   conda_file: xxx
        #   python_requirements_txt: xxx
        #   setup_sh: xxx
        # TODO: deserialize dag with structured class here to avoid using so many magic strings
        env_obj = flow_info.get("environment", {})

        from importlib.metadata import version

        env_obj["sdk_version"] = version("promptflow")
        # version 0.0.1 is the dev version of promptflow
        if env_obj["sdk_version"] == "0.0.1":
            del env_obj["sdk_version"]

        if not env_obj.get("python_requirements_txt", None) and (flow_dag_path.parent / "requirements.txt").is_file():
            env_obj["python_requirements_txt"] = "requirements.txt"

        env_obj["conda_env_name"] = "promptflow-serve"
        if "conda_file" in env_obj:
            conda_file = flow_dag_path.parent / env_obj["conda_file"]
            if conda_file.is_file():
                conda_obj = yaml.safe_load(conda_file.read_text())
                if "name" in conda_obj:
                    env_obj["conda_env_name"] = conda_obj["name"]

        return env_obj

    @classmethod
    def _dump_connection(cls, connection, output_path: Path):
        # connection yaml should be a dict instead of ordered dict
        connection_dict = connection._to_dict()
        connection_yaml = {
            "$schema": f"https://azuremlschemas.azureedge.net/promptflow/"
            f"latest/{connection.__class__.__name__}.schema.json",
            **connection_dict,
        }

        if connection.type == "Custom":
            secret_dict = connection_yaml["secrets"]
        else:
            secret_dict = connection_yaml

        secret_env_vars = [f"{connection.name}_{secret_key}".upper() for secret_key in connection.secrets]
        for secret_key, secret_env in zip(connection.secrets, secret_env_vars):
            secret_dict[secret_key] = "${env:" + secret_env + "}"

        for key in ["created_date", "last_modified_date"]:
            if key in connection_yaml:
                del connection_yaml[key]

        key_order = ["$schema", "type", "name", "configs", "secrets", "module"]
        sorted_connection_dict = {
            key: connection_yaml[key]
            for key in sorted(
                connection_yaml.keys(),
                key=lambda x: (0, key_order.index(x)) if x in key_order else (1, x),
            )
        }

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(dump_yaml(sorted_connection_dict, sort_keys=False))
        return secret_env_vars

    @classmethod
    def _migrate_connections(cls, connection_names: List[str], output_dir: Path):
        from promptflow._sdk._pf_client import PFClient

        output_dir.mkdir(parents=True, exist_ok=True)

        local_client = PFClient()
        connection_paths, secret_env_vars = [], {}
        for connection_name in connection_names:
            connection = local_client.connections.get(name=connection_name, with_secrets=True)
            connection_paths.append(output_dir / f"{connection_name}.yaml")
            for secret_env_var in cls._dump_connection(
                connection,
                connection_paths[-1],
            ):
                if secret_env_var in secret_env_vars:
                    raise RuntimeError(
                        f"environment variable name conflict: connection {connection_name} and "
                        f"{secret_env_vars[secret_env_var]} on {secret_env_var}"
                    )
                secret_env_vars[secret_env_var] = connection_name

        return connection_paths, list(secret_env_vars.keys())

    @classmethod
    def _export_to_docker(cls, flow_dag_path: Path, output_dir: Path, *, connection_paths: List[Path], flow_name: str):
        environment_config = cls._build_environment_config(flow_dag_path)

        # TODO: make below strings constants
        copy_tree_respect_template_and_ignore_file(
            source=Path(__file__).parent.parent / "data" / "docker",
            target=output_dir,
            render_context={
                "env": environment_config,
                "flow_name": f"{flow_name}-{generate_random_string(6)}",
                "local_db_rel_path": LOCAL_MGMT_DB_PATH.relative_to(Path.home()).as_posix(),
                "connection_yaml_paths": list(map(lambda x: x.relative_to(output_dir).as_posix(), connection_paths)),
            },
        )

    @classmethod
    def build(
        cls,
        flow: Union[str, PathLike],
        *,
        output: Union[str, PathLike],
        format: str = "docker",
        variant: str = None,
    ):
        """
        Build flow to other format.

        :param flow: path to the flow directory or flow dag to export
        :type flow: Union[str, PathLike]
        :param format: export format, support "docker" only for now
        :type format: str
        :param output: output directory
        :type output: Union[str, PathLike]
        :param variant: node variant in format of {node_name}.{variant_name},
            will use default variant if not specified.
        :type variant: str
        :return: no return
        :rtype: None
        """
        output_dir = Path(output)
        output_dir.mkdir(parents=True, exist_ok=True)

        flow_path = Path(flow)
        if flow_path.is_dir() and (flow_path / DAG_FILE_NAME).is_file():
            flow_dag_path = flow_path / DAG_FILE_NAME
        else:
            flow_dag_path = flow_path

        if not flow_dag_path.is_file():
            raise ValueError(f"Flow dag file {flow_dag_path.as_posix()} does not exist.")

        if format not in ["docker"]:
            raise ValueError(f"Unsupported export format: {format}")

        if variant:
            tuning_node, node_variant = parse_variant(variant)
        else:
            tuning_node, node_variant = None, None

        flow_copy_target = output_dir / "flow"
        flow_copy_target.mkdir(parents=True, exist_ok=True)

        # resolve additional includes and copy flow directory first to guarantee there is a final flow directory
        # TODO: avoid copy for twice
        with variant_overwrite_context(flow_dag_path, tuning_node=tuning_node, variant=node_variant) as temp_flow:
            from promptflow.contracts.flow import Flow as ExecutableFlow

            executable = ExecutableFlow.from_yaml(flow_file=temp_flow.path, working_dir=temp_flow.code)

            connection_paths, secret_env_vars = cls._migrate_connections(
                connection_names=executable.get_connection_names(),
                output_dir=output_dir / "connections",
            )
            (output_dir / "settings.json").write_text(
                data=json.dumps({secret_env_var: "" for secret_env_var in secret_env_vars}, indent=2),
                encoding="utf-8",
            )

            copy_tree_respect_template_and_ignore_file(temp_flow.code, flow_copy_target)

            if format == "docker":
                cls._export_to_docker(
                    flow_dag_path=temp_flow.path,
                    output_dir=output_dir,
                    connection_paths=connection_paths,
                    flow_name=flow_dag_path.parent.stem,
                )
