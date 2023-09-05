# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import contextlib
import json
from importlib.metadata import version
from os import PathLike
from pathlib import Path
from typing import Iterable, List, Tuple, Union

import yaml

from promptflow._sdk._constants import (
    BASE_PATH_CONTEXT_KEY,
    CHAT_HISTORY,
    DAG_FILE_NAME,
    DEFAULT_ENCODING,
    FLOW_TOOLS_JSON,
    LOCAL_MGMT_DB_PATH,
    PROMPT_FLOW_DIR_NAME,
)
from promptflow._sdk._utils import (
    _get_additional_includes,
    _merge_local_code_and_additional_includes,
    copy_tree_respect_template_and_ignore_file,
    dump_yaml,
    generate_flow_tools_json,
    generate_random_string,
    parse_variant,
)
from promptflow._sdk.operations._run_submitter import remove_additional_includes, variant_overwrite_context
from promptflow._sdk.operations._test_submitter import TestSubmitter
from promptflow.exceptions import ErrorTarget, UserErrorException


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
            is_chat_flow, chat_history_input_name, _ = self._is_chat_flow(submitter.dataplane_flow)
            if is_chat_flow and not inputs.get(chat_history_input_name, None):
                inputs[chat_history_input_name] = []
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
        chat_history_input_name = next(
            iter([input_name for input_name, value in flow.inputs.items() if value.is_chat_history]), None
        )
        if (
            not chat_history_input_name
            and CHAT_HISTORY in flow.inputs
            and flow.inputs[CHAT_HISTORY].is_chat_history is not False
        ):
            chat_history_input_name = CHAT_HISTORY
        is_chat_flow, error_msg = True, ""
        if len(chat_inputs) != 1:
            is_chat_flow = False
            error_msg = "chat flow does not support multiple chat inputs"
        elif len(chat_outputs) != 1:
            is_chat_flow = False
            error_msg = "chat flow does not support multiple chat outputs"
        elif not chat_history_input_name:
            is_chat_flow = False
            error_msg = "chat_history is required in the inputs of chat flow"
        return is_chat_flow, chat_history_input_name, error_msg

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
            is_chat_flow, chat_history_input_name, error_msg = self._is_chat_flow(submitter.dataplane_flow)
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
                chat_history_name=chat_history_input_name,
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

        env_var_names = [f"{connection.name}_{secret_key}".upper() for secret_key in connection.secrets]
        for secret_key, secret_env in zip(connection.secrets, env_var_names):
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
        return env_var_names

    @classmethod
    def _migrate_connections(cls, connection_names: List[str], output_dir: Path):
        from promptflow._sdk._pf_client import PFClient

        output_dir.mkdir(parents=True, exist_ok=True)

        local_client = PFClient()
        connection_paths, env_var_names = [], {}
        for connection_name in connection_names:
            connection = local_client.connections.get(name=connection_name, with_secrets=True)
            connection_paths.append(output_dir / f"{connection_name}.yaml")
            for env_var_name in cls._dump_connection(
                connection,
                connection_paths[-1],
            ):
                if env_var_name in env_var_names:
                    raise RuntimeError(
                        f"environment variable name conflict: connection {connection_name} and "
                        f"{env_var_names[env_var_name]} on {env_var_name}"
                    )
                env_var_names[env_var_name] = connection_name

        return connection_paths, list(env_var_names.keys())

    @classmethod
    def _export_flow_connections(
        cls,
        flow_dag_path: Path,
        *,
        output_dir: Path,
    ):
        from promptflow.contracts.flow import Flow as ExecutableFlow

        executable = ExecutableFlow.from_yaml(flow_file=Path(flow_dag_path.name), working_dir=flow_dag_path.parent)

        return cls._migrate_connections(
            connection_names=executable.get_connection_names(),
            output_dir=output_dir,
        )

    @classmethod
    def _build_flow(
        cls,
        flow_dag_path: Path,
        *,
        output: Union[str, PathLike],
        tuning_node: str = None,
        node_variant: str = None,
        update_flow_tools_json: bool = True,
    ):

        flow_copy_target = Path(output)
        flow_copy_target.mkdir(parents=True, exist_ok=True)

        # resolve additional includes and copy flow directory first to guarantee there is a final flow directory
        # TODO: shall we pop "node_variants" unless keep-variants is specified?
        with variant_overwrite_context(
            flow_dag_path,
            tuning_node=tuning_node,
            variant=node_variant,
            drop_node_variants=True,
        ) as temp_flow:
            # TODO: avoid copy for twice
            copy_tree_respect_template_and_ignore_file(temp_flow.code, flow_copy_target)
        if update_flow_tools_json:
            generate_flow_tools_json(flow_copy_target)
        return flow_copy_target / flow_dag_path.name

    @classmethod
    def _export_to_docker(
        cls,
        flow_dag_path: Path,
        output_dir: Path,
        *,
        env_var_names: List[str],
        connection_paths: List[Path],
        flow_name: str,
    ):
        (output_dir / "settings.json").write_text(
            data=json.dumps({env_var_name: "" for env_var_name in env_var_names}, indent=2),
            encoding="utf-8",
        )

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
        **kwargs,
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

        flow_only = kwargs.pop("flow_only", False)
        if flow_only:
            output_flow_dir = output_dir
        else:
            output_flow_dir = output_dir / "flow"

        new_flow_dag_path = cls._build_flow(
            flow_dag_path=flow_dag_path,
            output=output_flow_dir,
            tuning_node=tuning_node,
            node_variant=node_variant,
        )

        if flow_only:
            return

        # use new flow dag path below as origin one may miss additional includes
        connection_paths, env_var_names = cls._export_flow_connections(
            flow_dag_path=new_flow_dag_path,
            output_dir=output_dir / "connections",
        )

        if format == "docker":
            cls._export_to_docker(
                flow_dag_path=new_flow_dag_path,
                output_dir=output_dir,
                connection_paths=connection_paths,
                flow_name=flow_dag_path.parent.stem,
                env_var_names=env_var_names,
            )

    @classmethod
    @contextlib.contextmanager
    def _resolve_additional_includes(cls, flow_dag_path: Path) -> Iterable[Path]:
        if _get_additional_includes(flow_dag_path):
            # Merge the flow folder and additional includes to temp folder.
            # TODO: support a flow_dag_path with a name different from flow.dag.yaml
            with _merge_local_code_and_additional_includes(code_path=flow_dag_path.parent) as temp_dir:
                remove_additional_includes(Path(temp_dir))
                yield Path(temp_dir) / flow_dag_path.name
        else:
            yield flow_dag_path

    def validate(self, flow: Union[str, PathLike], *, raise_error: bool = False, **kwargs) -> dict:
        """
        Validate flow.

        :param flow: path to the flow directory or flow dag to export
        :type flow: Union[str, PathLike]
        :param raise_error: whether raise error when validation failed
        :type raise_error: bool
        :return: dict of validation result
        :rtype: dict
        """

        flow_path = Path(flow)
        if flow_path.is_dir() and (flow_path / DAG_FILE_NAME).is_file():
            flow_dag_path = flow_path / DAG_FILE_NAME
        else:
            flow_dag_path = flow_path

        if not flow_dag_path.is_file():
            raise ValueError(f"Flow dag file {flow_dag_path.as_posix()} does not exist.")

        # TODO: put off this if we do path existence check in FlowSchema on fields other than additional_includes
        flow_dag_obj = yaml.safe_load(flow_dag_path.read_text(encoding=DEFAULT_ENCODING))
        from promptflow._sdk.schemas._flow import FlowSchema

        # TODO: check path existence of additional_includes in FlowSchema
        validation_result = FlowSchema(context={BASE_PATH_CONTEXT_KEY: flow_dag_path.parent}).validate(flow_dag_obj)

        with self._resolve_additional_includes(flow_dag_path) as new_flow_dag_path:
            flow_tools = generate_flow_tools_json(
                flow_directory=new_flow_dag_path.parent,
                dump=False,
                raise_error=False,
                include_errors_in_output=True,
            )
            tools_errors = {}
            if "code" in flow_tools:
                nodes_with_error = [
                    node_name for node_name, message in flow_tools["code"].items() if isinstance(message, str)
                ]
                for node_name in nodes_with_error:
                    tools_errors[node_name] = flow_tools["code"].pop(node_name)

        # generate flow tools json
        flow_tools_json_path = flow_dag_path.parent / PROMPT_FLOW_DIR_NAME / FLOW_TOOLS_JSON

        flow_tools_json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(flow_tools_json_path, "w", encoding=DEFAULT_ENCODING) as f:
            json.dump(flow_tools, f, indent=4)

        if tools_errors:
            validation_result["tool-meta"] = tools_errors

        if validation_result and raise_error:
            raise UserErrorException(
                "Validation failed:\n%s" % json.dumps(validation_result, indent=4),
                target=ErrorTarget.CONTROL_PLANE_SDK,
            )

        # TODO: convert return value to a ValidationResult object
        return validation_result

    def _generate_tools_meta(
        self,
        flow: Union[str, PathLike],
        *,
        source_name: str = None,
    ) -> Tuple[dict, dict]:
        """Generate flow tools meta for a specific flow or a specific node in the flow.

        This is a private interface for vscode extension, so do not change the interface unless necessary.
        Sample output:
        (
            {
                "convert_to_dict.py": {
                    "type": "python",
                    "inputs": {
                        "input_str": {
                            "type": [
                                "string"
                            ]
                        }
                    },
                    "source": "convert_to_dict.py",
                    "function": "convert_to_dict"
                }
            },
            {
                "summarize_text_content__variant_1.jinja2": "File not found: summarize_text_content__variant_1.jinja2"
            }
        )

        Usage:
        from promptflow import PFClient
        PFClient().flows._generate_tools_meta(flow="flow.dag.yaml", source_name="convert_to_dict.py")

        :param flow: path to the flow directory or flow dag to export
        :type flow: Union[str, PathLike]
        :param source_name: source name to generate tools meta. If not specified, generate tools meta for all sources.
        :type source_name: str
        :return: dict of tools meta and dict of tools errors
        :rtype: Tuple[dict, dict]
        """
        flow_path = Path(flow)
        if flow_path.is_dir() and (flow_path / DAG_FILE_NAME).is_file():
            flow_dag_path = flow_path / DAG_FILE_NAME
        else:
            flow_dag_path = flow_path

        if not flow_dag_path.is_file():
            raise ValueError(f"Flow dag file {flow_dag_path.as_posix()} does not exist.")

        with self._resolve_additional_includes(flow_dag_path) as new_flow_dag_path:
            flow_tools = generate_flow_tools_json(
                flow_directory=new_flow_dag_path.parent,
                dump=False,
                raise_error=False,
                include_errors_in_output=True,
            )

        # TODO: do you need flow.tools.json['package']?
        flow_tools_meta = flow_tools.pop("code", {})
        if source_name:
            if source_name not in flow_tools_meta:
                raise ValueError(f"Source {source_name} does not exist in flow {flow_dag_path.as_posix()}")
            flow_tools_meta = {source_name: flow_tools_meta[source_name]}

        tools_errors = {}
        nodes_with_error = [node_name for node_name, message in flow_tools_meta.items() if isinstance(message, str)]
        for node_name in nodes_with_error:
            tools_errors[node_name] = flow_tools_meta.pop(node_name)

        return flow_tools_meta, tools_errors
