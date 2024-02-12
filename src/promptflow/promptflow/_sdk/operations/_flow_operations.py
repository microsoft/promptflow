# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import contextlib
import glob
import json
import os
import subprocess
import sys
import uuid
from importlib.metadata import version
from os import PathLike
from pathlib import Path
from typing import Dict, Iterable, List, Tuple, Union

from promptflow._constants import FlowLanguage
from promptflow._sdk._configuration import Configuration
from promptflow._sdk._constants import CHAT_HISTORY, DEFAULT_ENCODING, FLOW_TOOLS_JSON_GEN_TIMEOUT, LOCAL_MGMT_DB_PATH
from promptflow._sdk._load_functions import load_flow
from promptflow._sdk._submitter import TestSubmitter
from promptflow._sdk._submitter.utils import SubmitterHelper
from promptflow._sdk._telemetry import ActivityType, TelemetryMixin, monitor_operation
from promptflow._sdk._utils import (
    _get_additional_includes,
    _merge_local_code_and_additional_includes,
    copy_tree_respect_template_and_ignore_file,
    dump_flow_result,
    generate_flow_tools_json,
    generate_random_string,
    logger,
    parse_variant,
)
from promptflow._sdk.entities._eager_flow import EagerFlow
from promptflow._sdk.entities._flow import Flow, FlowBase, ProtectedFlow
from promptflow._sdk.entities._validation import ValidationResult
from promptflow._utils.context_utils import _change_working_dir
from promptflow._utils.yaml_utils import dump_yaml, load_yaml
from promptflow.exceptions import UserErrorException


class FlowOperations(TelemetryMixin):
    """FlowOperations."""

    def __init__(self, client):
        self._client = client
        super().__init__()

    @monitor_operation(activity_name="pf.flows.test", activity_type=ActivityType.PUBLICAPI)
    def test(
        self,
        flow: Union[str, PathLike],
        *,
        inputs: dict = None,
        variant: str = None,
        node: str = None,
        environment_variables: dict = None,
        entry: str = None,
        **kwargs,
    ) -> dict:
        """Test flow or node.

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
        experiment = kwargs.pop("experiment", None)
        output_path = kwargs.get("output_path", None)
        if Configuration.get_instance().is_internal_features_enabled() and experiment:
            return self._client._experiments._test(
                flow=flow,
                inputs=inputs,
                environment_variables=environment_variables,
                experiment=experiment,
                **kwargs,
            )

        result = self._test(
            flow=flow,
            inputs=inputs,
            variant=variant,
            node=node,
            environment_variables=environment_variables,
            **kwargs,
        )

        dump_test_result = kwargs.get("dump_test_result", False)
        if dump_test_result:
            # Dump flow/node test info
            flow = load_flow(flow)
            if node:
                dump_flow_result(
                    flow_folder=flow.code, node_result=result, prefix=f"flow-{node}.node", custom_path=output_path
                )
            else:
                if variant:
                    tuning_node, node_variant = parse_variant(variant)
                    prefix = f"flow-{tuning_node}-{node_variant}"
                else:
                    prefix = "flow"
                dump_flow_result(
                    flow_folder=flow.code,
                    flow_result=result,
                    prefix=prefix,
                    custom_path=output_path,
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
        stream_output: bool = True,
        allow_generator_output: bool = True,
        **kwargs,
    ):
        """Test flow or node.

        :param flow: path to flow directory to test
        :param inputs: Input data for the flow test
        :param variant: Node & variant name in format of ${node_name.variant_name}, will use default variant
           if not specified.
        :param node: If specified it will only test this node, else it will test the flow.
        :param environment_variables: Environment variables to set by specifying a property path and value.
           Example: {"key1": "${my_connection.api_key}", "key2"="value2"}
           The value reference to connection keys will be resolved to the actual value,
           and all environment variables specified will be set into os.environ.
        :param stream_log: Whether streaming the log.
        :param stream_output: Whether streaming the outputs.
        :param allow_generator_output: Whether return streaming output when flow has streaming output.
        :return: Executor result
        """
        from promptflow._sdk._load_functions import load_flow

        inputs = inputs or {}
        output_path = kwargs.get("output_path", None)
        session = kwargs.pop("session", None)
        # Run id will be set in operation context and used for session
        run_id = kwargs.get("run_id", str(uuid.uuid4()))
        flow: FlowBase = load_flow(flow)

        if isinstance(flow, EagerFlow):
            if variant or node:
                logger.warning("variant and node are not supported for eager flow, will be ignored")
                variant, node = None, None
        flow.context.variant = variant

        with TestSubmitter(flow=flow, flow_context=flow.context, client=self._client).init(
            target_node=node,
            environment_variables=environment_variables,
            stream_log=stream_log,
            output_path=output_path,
            stream_output=stream_output,
            session=session,
        ) as submitter:
            if isinstance(flow, EagerFlow):
                # TODO(2897153): support chat eager flow
                is_chat_flow, chat_history_input_name = False, None
                flow_inputs, dependency_nodes_outputs = inputs, None
            else:
                is_chat_flow, chat_history_input_name, _ = self._is_chat_flow(submitter.dataplane_flow)
                flow_inputs, dependency_nodes_outputs = submitter.resolve_data(
                    node_name=node, inputs=inputs, chat_history_name=chat_history_input_name
                )

            if node:
                return submitter.node_test(
                    flow_inputs=flow_inputs,
                    dependency_nodes_outputs=dependency_nodes_outputs,
                )
            else:
                return submitter.flow_test(
                    inputs=flow_inputs,
                    allow_generator_output=allow_generator_output and is_chat_flow,
                    run_id=run_id,
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

    @monitor_operation(activity_name="pf.flows._chat", activity_type=ActivityType.INTERNALCALL)
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

        flow: FlowBase = load_flow(flow)
        flow.context.variant = variant

        with TestSubmitter(flow=flow, flow_context=flow.context, client=self._client).init(
            environment_variables=environment_variables,
            stream_log=False,  # no need to stream log in chat mode
        ) as submitter:
            is_chat_flow, chat_history_input_name, error_msg = self._is_chat_flow(submitter.dataplane_flow)
            if not is_chat_flow:
                raise UserErrorException(f"Only support chat flow in interactive mode, {error_msg}.")

            info_msg = f"Welcome to chat flow, {submitter.dataplane_flow.name}."
            print("=" * len(info_msg))
            print(info_msg)
            print("Press Enter to send your message.")
            print("You can quit with ctrl+C.")
            print("=" * len(info_msg))

            submitter._chat_flow(
                inputs=inputs,
                chat_history_name=chat_history_input_name,
                show_step_output=kwargs.get("show_step_output", False),
            )

    @monitor_operation(activity_name="pf.flows._chat_with_ui", activity_type=ActivityType.INTERNALCALL)
    def _chat_with_ui(self, script):
        try:
            import bs4  # noqa: F401
            import streamlit_quill  # noqa: F401
            from streamlit.web import cli as st_cli
        except ImportError as ex:
            raise UserErrorException(
                f"Please try 'pip install promptflow[executable]' to install dependency, {ex.msg}."
            )
        sys.argv = [
            "streamlit",
            "run",
            script,
            "--global.developmentMode=false",
            "--client.toolbarMode=viewer",
            "--browser.gatherUsageStats=false",
        ]
        st_cli.main()

    def _build_environment_config(self, flow_dag_path: Path):
        flow_info = load_yaml(flow_dag_path)
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
                conda_obj = load_yaml(conda_file)
                if "name" in conda_obj:
                    env_obj["conda_env_name"] = conda_obj["name"]

        return env_obj

    @classmethod
    def _refine_connection_name(cls, connection_name: str):
        return connection_name.replace(" ", "_")

    def _dump_connection(self, connection, output_path: Path):
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

        connection_var_name = self._refine_connection_name(connection.name)
        env_var_names = [f"{connection_var_name}_{secret_key}".upper() for secret_key in connection.secrets]
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
            f.write(dump_yaml(sorted_connection_dict))
        return env_var_names

    def _migrate_connections(self, connection_names: List[str], output_dir: Path):
        from promptflow._sdk._pf_client import PFClient

        output_dir.mkdir(parents=True, exist_ok=True)

        local_client = PFClient()
        connection_paths, env_var_names = [], {}
        for connection_name in connection_names:
            connection = local_client.connections.get(name=connection_name, with_secrets=True)
            connection_var_name = self._refine_connection_name(connection_name)
            connection_paths.append(output_dir / f"{connection_var_name}.yaml")
            for env_var_name in self._dump_connection(
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

    def _export_flow_connections(
        self,
        built_flow_dag_path: Path,
        *,
        output_dir: Path,
    ):
        """Export flow connections to yaml files.

        :param built_flow_dag_path: path to built flow dag yaml file. Given this is a built flow, we can assume
        that the flow involves no additional includes, symlink, or variant.
        :param output_dir: output directory to export connections
        """
        flow: FlowBase = load_flow(built_flow_dag_path)
        with _change_working_dir(flow.code):
            if flow.language == FlowLanguage.CSharp:
                from promptflow.batch import CSharpExecutorProxy

                return self._migrate_connections(
                    connection_names=SubmitterHelper.get_used_connection_names(
                        tools_meta=CSharpExecutorProxy.get_tool_metadata(
                            flow_file=flow.flow_dag_path,
                            working_dir=flow.code,
                        ),
                        flow_dag=flow._data,
                    ),
                    output_dir=output_dir,
                )
            else:
                # TODO: avoid using executable here
                from promptflow.contracts.flow import Flow as ExecutableFlow

                executable = ExecutableFlow.from_yaml(flow_file=flow.path, working_dir=flow.code)
                return self._migrate_connections(
                    connection_names=executable.get_connection_names(),
                    output_dir=output_dir,
                )

    def _build_flow(
        self,
        flow: Flow,
        *,
        output: Union[str, PathLike],
        tuning_node: str = None,
        node_variant: str = None,
        update_flow_tools_json: bool = True,
    ):
        # TODO: confirm if we need to import this
        from promptflow._sdk._submitter import variant_overwrite_context

        flow_copy_target = Path(output)
        flow_copy_target.mkdir(parents=True, exist_ok=True)

        # resolve additional includes and copy flow directory first to guarantee there is a final flow directory
        # TODO: shall we pop "node_variants" unless keep-variants is specified?
        with variant_overwrite_context(
            flow=flow,
            tuning_node=tuning_node,
            variant=node_variant,
            drop_node_variants=True,
        ) as temp_flow:
            # TODO: avoid copy for twice
            copy_tree_respect_template_and_ignore_file(temp_flow.code, flow_copy_target)
        if update_flow_tools_json:
            generate_flow_tools_json(flow_copy_target)
        return flow_copy_target / flow.path.name

    def _export_to_docker(
        self,
        flow_dag_path: Path,
        output_dir: Path,
        *,
        env_var_names: List[str],
        connection_paths: List[Path],
        flow_name: str,
        is_csharp_flow: bool = False,
    ):
        (output_dir / "settings.json").write_text(
            data=json.dumps({env_var_name: "" for env_var_name in env_var_names}, indent=2),
            encoding="utf-8",
        )

        environment_config = self._build_environment_config(flow_dag_path)

        # TODO: make below strings constants
        if is_csharp_flow:
            source = Path(__file__).parent.parent / "data" / "docker_csharp"
        else:
            source = Path(__file__).parent.parent / "data" / "docker"
        copy_tree_respect_template_and_ignore_file(
            source=source,
            target=output_dir,
            render_context={
                "env": environment_config,
                "flow_name": f"{flow_name}-{generate_random_string(6)}",
                "local_db_rel_path": LOCAL_MGMT_DB_PATH.relative_to(Path.home()).as_posix(),
                "connection_yaml_paths": list(map(lambda x: x.relative_to(output_dir).as_posix(), connection_paths)),
            },
        )

    def _build_as_executable(
        self,
        flow_dag_path: Path,
        output_dir: Path,
        *,
        flow_name: str,
        env_var_names: List[str],
    ):
        try:
            import bs4  # noqa: F401
            import PyInstaller  # noqa: F401
            import streamlit
            import streamlit_quill  # noqa: F401
        except ImportError as ex:
            raise UserErrorException(
                f"Please try 'pip install promptflow[executable]' to install dependency, {ex.msg}."
            )

        from promptflow.contracts.flow import Flow as ExecutableFlow

        (output_dir / "settings.json").write_text(
            data=json.dumps({env_var_name: "" for env_var_name in env_var_names}, indent=2),
            encoding="utf-8",
        )

        environment_config = self._build_environment_config(flow_dag_path)
        hidden_imports = []
        if (
            environment_config.get("python_requirements_txt", None)
            and (flow_dag_path.parent / "requirements.txt").is_file()
        ):
            with open(flow_dag_path.parent / "requirements.txt", "r", encoding="utf-8") as file:
                file_content = file.read()
            hidden_imports = file_content.splitlines()

        runtime_interpreter_path = (Path(streamlit.__file__).parent / "runtime").as_posix()

        executable = ExecutableFlow.from_yaml(flow_file=Path(flow_dag_path.name), working_dir=flow_dag_path.parent)
        flow_inputs = {
            flow_input: (value.default, value.type.value)
            for flow_input, value in executable.inputs.items()
            if not value.is_chat_history
        }
        flow_inputs_params = ["=".join([flow_input, flow_input]) for flow_input, _ in flow_inputs.items()]
        flow_inputs_params = ",".join(flow_inputs_params)

        is_chat_flow, chat_history_input_name, _ = self._is_chat_flow(executable)
        label = "Chat" if is_chat_flow else "Run"
        copy_tree_respect_template_and_ignore_file(
            source=Path(__file__).parent.parent / "data" / "executable",
            target=output_dir,
            render_context={
                "hidden_imports": hidden_imports,
                "flow_name": flow_name,
                "runtime_interpreter_path": runtime_interpreter_path,
                "flow_inputs": flow_inputs,
                "flow_inputs_params": flow_inputs_params,
                "flow_path": None,
                "is_chat_flow": is_chat_flow,
                "chat_history_input_name": chat_history_input_name,
                "label": label,
            },
        )
        self._run_pyinstaller(output_dir)

    def _run_pyinstaller(self, output_dir):
        with _change_working_dir(output_dir, mkdir=False):
            subprocess.run(["pyinstaller", "app.spec"], check=True)
            print("PyInstaller command executed successfully.")

    @monitor_operation(activity_name="pf.flows.build", activity_type=ActivityType.PUBLICAPI)
    def build(
        self,
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
        :param format: export format, support "docker" and "executable" only for now
        :type format: str
        :param output: output directory
        :type output: Union[str, PathLike]
        :param variant: node variant in format of {node_name}.{variant_name},
            will use default variant if not specified.
        :type variant: str
        :return: no return
        :rtype: None
        """
        output_dir = Path(output).absolute()
        output_dir.mkdir(parents=True, exist_ok=True)

        flow: FlowBase = load_flow(flow)
        is_csharp_flow = flow.language == FlowLanguage.CSharp

        if format not in ["docker", "executable"]:
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

        new_flow_dag_path = self._build_flow(
            flow=flow,
            output=output_flow_dir,
            tuning_node=tuning_node,
            node_variant=node_variant,
            update_flow_tools_json=False if is_csharp_flow else True,
        )

        if flow_only:
            return

        # use new flow dag path below as origin one may miss additional includes
        connection_paths, env_var_names = self._export_flow_connections(
            built_flow_dag_path=new_flow_dag_path,
            output_dir=output_dir / "connections",
        )

        if format == "docker":
            self._export_to_docker(
                flow_dag_path=new_flow_dag_path,
                output_dir=output_dir,
                connection_paths=connection_paths,
                flow_name=flow.name,
                env_var_names=env_var_names,
                is_csharp_flow=is_csharp_flow,
            )
        elif format == "executable":
            self._build_as_executable(
                flow_dag_path=new_flow_dag_path,
                output_dir=output_dir,
                flow_name=flow.name,
                env_var_names=env_var_names,
            )

    @classmethod
    @contextlib.contextmanager
    def _resolve_additional_includes(cls, flow_dag_path: Path) -> Iterable[Path]:
        # TODO: confirm if we need to import this
        from promptflow._sdk._submitter import remove_additional_includes

        # Eager flow may not contain a yaml file, skip resolving additional includes
        def is_yaml_file(file_path):
            _, file_extension = os.path.splitext(file_path)
            return file_extension.lower() in (".yaml", ".yml")

        if is_yaml_file(flow_dag_path) and _get_additional_includes(flow_dag_path):
            # Merge the flow folder and additional includes to temp folder.
            # TODO: support a flow_dag_path with a name different from flow.dag.yaml
            with _merge_local_code_and_additional_includes(code_path=flow_dag_path.parent) as temp_dir:
                remove_additional_includes(Path(temp_dir))
                yield Path(temp_dir) / flow_dag_path.name
        else:
            yield flow_dag_path

    @monitor_operation(activity_name="pf.flows.validate", activity_type=ActivityType.PUBLICAPI)
    def validate(self, flow: Union[str, PathLike], *, raise_error: bool = False, **kwargs) -> ValidationResult:
        """
        Validate flow.

        :param flow: path to the flow directory or flow dag to export
        :type flow: Union[str, PathLike]
        :param raise_error: whether raise error when validation failed
        :type raise_error: bool
        :return: a validation result object
        :rtype: ValidationResult
        """

        flow_entity: ProtectedFlow = load_flow(source=flow)

        # TODO: put off this if we do path existence check in FlowSchema on fields other than additional_includes
        validation_result = flow_entity._validate()

        source_path_mapping = {}
        flow_tools, tools_errors = self._generate_tools_meta(
            flow=flow_entity.flow_dag_path,
            source_path_mapping=source_path_mapping,
        )

        flow_entity.tools_meta_path.write_text(
            data=json.dumps(flow_tools, indent=4),
            encoding=DEFAULT_ENCODING,
        )

        if tools_errors:
            for source_name, message in tools_errors.items():
                for yaml_path in source_path_mapping.get(source_name, []):
                    validation_result.append_error(
                        yaml_path=yaml_path,
                        message=message,
                    )

        # flow in control plane is read-only, so resolve location makes sense even in SDK experience
        validation_result.resolve_location_for_diagnostics(flow_entity.flow_dag_path.as_posix())

        flow_entity._try_raise(
            validation_result,
            raise_error=raise_error,
        )

        return validation_result

    @monitor_operation(activity_name="pf.flows._generate_tools_meta", activity_type=ActivityType.INTERNALCALL)
    def _generate_tools_meta(
        self,
        flow: Union[str, PathLike],
        *,
        source_name: str = None,
        source_path_mapping: Dict[str, List[str]] = None,
        timeout: int = FLOW_TOOLS_JSON_GEN_TIMEOUT,
    ) -> Tuple[dict, dict]:
        """Generate flow tools meta for a specific flow or a specific node in the flow.

        This is a private interface for vscode extension, so do not change the interface unless necessary.

        Usage:
        from promptflow import PFClient
        PFClient().flows._generate_tools_meta(flow="flow.dag.yaml", source_name="convert_to_dict.py")

        :param flow: path to the flow directory or flow dag to export
        :type flow: Union[str, PathLike]
        :param source_name: source name to generate tools meta. If not specified, generate tools meta for all sources.
        :type source_name: str
        :param source_path_mapping: If passed in None, do nothing; if passed in a dict, will record all reference yaml
                                    paths for each source in the dict passed in.
        :type source_path_mapping: Dict[str, List[str]]
        :param timeout: timeout for generating tools meta
        :type timeout: int
        :return: dict of tools meta and dict of tools errors
        :rtype: Tuple[dict, dict]
        """
        flow: FlowBase = load_flow(source=flow)
        if not isinstance(flow, ProtectedFlow):
            # No tools meta for eager flow
            return {}, {}

        with self._resolve_additional_includes(flow.flow_dag_path) as new_flow_dag_path:
            flow_tools = generate_flow_tools_json(
                flow_directory=new_flow_dag_path.parent,
                dump=False,
                raise_error=False,
                include_errors_in_output=True,
                target_source=source_name,
                used_packages_only=True,
                source_path_mapping=source_path_mapping,
                timeout=timeout,
            )

        flow_tools_meta = flow_tools.pop("code", {})

        tools_errors = {}
        nodes_with_error = [node_name for node_name, message in flow_tools_meta.items() if isinstance(message, str)]
        for node_name in nodes_with_error:
            tools_errors[node_name] = flow_tools_meta.pop(node_name)

        additional_includes = _get_additional_includes(flow.flow_dag_path)
        if additional_includes:
            additional_files = {}
            for include in additional_includes:
                include_path = Path(include) if Path(include).is_absolute() else flow.code / include
                if include_path.is_file():
                    file_name = Path(include).name
                    additional_files[Path(file_name)] = os.path.relpath(include_path, flow.code)
                else:
                    if not Path(include).is_absolute():
                        include = flow.code / include
                    files = glob.glob(os.path.join(include, "**"), recursive=True)
                    additional_files.update(
                        {
                            Path(os.path.relpath(path, include.parent)): os.path.relpath(path, flow.code)
                            for path in files
                        }
                    )
            for tool in flow_tools_meta.values():
                source = tool.get("source", None)
                if source and Path(source) in additional_files:
                    tool["source"] = additional_files[Path(source)]

        flow_tools["code"] = flow_tools_meta

        return flow_tools, tools_errors
