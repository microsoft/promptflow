# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import contextlib
import copy
import glob
import inspect
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import uuid
from dataclasses import MISSING, fields
from importlib.metadata import version
from os import PathLike
from pathlib import Path
from typing import Callable, Dict, Iterable, List, NoReturn, Optional, Tuple, Union

import pydash

from promptflow._constants import FLOW_FLEX_YAML, LANGUAGE_KEY, PROMPT_FLOW_DIR_NAME, FlowLanguage
from promptflow._proxy import ProxyFactory
from promptflow._sdk._configuration import Configuration
from promptflow._sdk._constants import (
    DEFAULT_ENCODING,
    DEFAULT_REQUIREMENTS_FILE_NAME,
    FLOW_META_JSON_GEN_TIMEOUT,
    FLOW_TOOLS_JSON_GEN_TIMEOUT,
    LOCAL_MGMT_DB_PATH,
    SERVE_SAMPLE_JSON_PATH,
)
from promptflow._sdk._load_functions import load_flow
from promptflow._sdk._orchestrator import TestSubmitter
from promptflow._sdk._orchestrator.utils import SubmitterHelper
from promptflow._sdk._telemetry import ActivityType, TelemetryMixin, monitor_operation
from promptflow._sdk._utilities.general_utils import (
    _get_additional_includes,
    _merge_local_code_and_additional_includes,
    add_executable_script_to_env_path,
    copy_tree_respect_template_and_ignore_file,
    generate_flow_tools_json,
    generate_random_string,
    generate_yaml_entry_without_delete,
    json_load,
    logger,
)
from promptflow._sdk._utilities.signature_utils import (
    format_signature_type,
    infer_signature_for_flex_flow,
    merge_flow_signature,
)
from promptflow._sdk.entities._flows import FlexFlow, Flow, Prompty
from promptflow._sdk.entities._validation import ValidationResult
from promptflow._utils.context_utils import _change_working_dir
from promptflow._utils.flow_utils import (
    dump_flow_result,
    get_flow_type,
    is_executable_chat_flow,
    is_flex_flow,
    is_prompty_flow,
    parse_variant,
)
from promptflow._utils.yaml_utils import dump_yaml, load_yaml
from promptflow.core._utils import init_executable, load_inputs_from_sample
from promptflow.exceptions import ErrorTarget, UserErrorException


class FlowOperations(TelemetryMixin):
    """FlowOperations."""

    def __init__(self, client, **kwargs):
        super().__init__(**kwargs)
        self._client = client

    @monitor_operation(activity_name="pf.flows.test", activity_type=ActivityType.PUBLICAPI)
    def test(
        self,
        flow: Union[str, PathLike],
        *,
        inputs: dict = None,
        variant: str = None,
        node: str = None,
        environment_variables: dict = None,
        init: Optional[dict] = None,
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
        :param init: Initialization parameters for flex flow, only supported when flow is callable class.
        :type init: dict
        :return: The result of flow or node
        :rtype: dict
        """
        experiment = kwargs.pop("experiment", None)
        flow = generate_yaml_entry_without_delete(entry=flow)
        if Configuration.get_instance().is_internal_features_enabled() and experiment:
            if variant is not None or node is not None:
                error = ValueError("--variant or --node is not supported experiment is specified.")
                raise UserErrorException(
                    target=ErrorTarget.CONTROL_PLANE_SDK,
                    message=str(error),
                    error=error,
                )
            return self._client._experiments._test_flow(
                flow=flow,
                inputs=inputs,
                environment_variables=environment_variables,
                experiment=experiment,
                init=init,
                **kwargs,
            )
        elif is_prompty_flow(flow):
            # For prompty flow, if output path is not specified, set output folder to .promptflow/prompty_file_name.
            # To avoid overwriting the execution info of different prompty in the same working dir.
            kwargs["output_path"] = (
                kwargs.get("output_path", None) or Path(flow).parent.resolve() / PROMPT_FLOW_DIR_NAME / Path(flow).stem
            )
        output_path = kwargs.get("output_path", None)
        result = self._test(
            flow=flow,
            inputs=inputs,
            variant=variant,
            node=node,
            environment_variables=environment_variables,
            init=init,
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

    def _test_with_ui(
        self,
        flow: Union[str, PathLike],
        output_path: PathLike,
        *,
        inputs: dict = None,
        variant: str = None,
        node: str = None,
        environment_variables: dict = None,
        entry: str = None,
        **kwargs,
    ) -> dict:
        """Test flow or node by http request.

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
        # The api is used for ux calling pfs. We need the api to read detail.json and log and return to ux as the
        # format they expected.
        experiment = kwargs.get("experiment", None)
        result = self.test(
            flow=flow,
            inputs=inputs,
            environment_variables=environment_variables,
            variant=variant,
            node=node,
            output_path=output_path,
            **kwargs,
        )
        if Configuration.get_instance().is_internal_features_enabled() and experiment:
            return_output = {}
            for key in result:
                detail_path = output_path / key / "flow.detail.json"
                log_path = output_path / key / "flow.log"
                detail_content = json_load(detail_path)
                with open(log_path, "r") as file:
                    log_content = file.read()
                return_output[key] = {
                    "detail": detail_content,
                    "log": log_content,
                    "output_path": str(output_path / key),
                }
        else:
            if node:
                detail_path = output_path / f"flow-{node}.node.detail.json"
                log_path = output_path / f"{node}.node.log"
            else:
                if variant:
                    tuning_node, node_variant = parse_variant(variant)
                    detail_path = output_path / f"flow-{tuning_node}-{node_variant}.detail.json"
                else:
                    detail_path = output_path / "flow.detail.json"
                log_path = output_path / "flow.log"
            detail_content = json_load(detail_path)
            with open(log_path, "r") as file:
                log_content = file.read()
            return_output = {"flow": {"detail": detail_content, "log": log_content, "output_path": str(output_path)}}
        return return_output

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
        init: Optional[dict] = None,
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
        :param init: Initialization parameters for flex flow, only supported when flow is callable class.
        :return: Executor result
        """
        output_path = kwargs.get("output_path", None)
        session = kwargs.pop("session", None)
        collection = kwargs.pop("collection", None)
        # Run id will be set in operation context and used for session
        run_id = kwargs.get("run_id", str(uuid.uuid4()))
        flow = load_flow(flow)

        if isinstance(flow, FlexFlow):
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
            init_kwargs=init,
            collection=collection,
        ) as submitter:
            # Only override sample inputs for prompty, flex flow and prompty has different sample format
            if isinstance(flow, Prompty) and not inputs:
                inputs = load_inputs_from_sample(submitter.flow.sample)
            is_chat_flow, chat_history_input_name, _ = is_executable_chat_flow(submitter.dataplane_flow)
            if isinstance(flow, FlexFlow) or isinstance(flow, Prompty):
                flow_inputs, dependency_nodes_outputs = inputs, None
            else:
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
                    init_kwargs=init,
                )

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

        flow = generate_yaml_entry_without_delete(entry=flow)
        flow = load_flow(flow)
        flow.context.variant = variant

        with TestSubmitter(flow=flow, flow_context=flow.context, client=self._client).init(
            environment_variables=environment_variables,
            stream_log=False,  # no need to stream log in chat mode
            collection=kwargs.get("collection", None),
        ) as submitter:
            is_chat_flow, chat_history_input_name, error_msg = is_executable_chat_flow(submitter.dataplane_flow)
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
    def _chat_with_ui(self, script, skip_open_browser: bool = False):
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
        if skip_open_browser:
            sys.argv += ["--server.headless=true"]
        st_cli.main()

    def _build_environment_config(self, flow_dag_path: Path):
        if is_prompty_flow(file_path=flow_dag_path):
            env_obj = {}
        else:
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
        flow = load_flow(built_flow_dag_path)
        with _change_working_dir(flow.code):
            if flow.language == FlowLanguage.CSharp:
                from promptflow._proxy._csharp_executor_proxy import CSharpExecutorProxy

                return self._migrate_connections(
                    connection_names=SubmitterHelper.get_used_connection_names(
                        tools_meta=CSharpExecutorProxy.generate_flow_tools_json(
                            flow_file=flow._flow_file_path,
                            working_dir=flow.code,
                        ),
                        flow_dag=flow._data,
                    ),
                    output_dir=output_dir,
                )
            else:
                # TODO: avoid using executable here
                executable = init_executable(flow_path=flow.path, working_dir=flow.code)
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
        from promptflow._sdk._orchestrator import flow_overwrite_context

        flow_copy_target = Path(output)
        flow_copy_target.mkdir(parents=True, exist_ok=True)

        # resolve additional includes and copy flow directory first to guarantee there is a final flow directory
        # TODO: shall we pop "node_variants" unless keep-variants is specified?
        with flow_overwrite_context(
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

        is_chat_flow, chat_history_input_name, _ = is_executable_chat_flow(executable)
        chat_output_name = next(
            filter(
                lambda key: executable.outputs[key].is_chat_output,
                executable.outputs.keys(),
            ),
            None,
        )
        label = "Chat" if is_chat_flow else "Run"
        is_streaming = True if is_chat_flow else False
        config_content = {
            "flow_name": flow_name,
            "flow_inputs": flow_inputs,
            "flow_path": flow_dag_path.as_posix(),
            "is_chat_flow": is_chat_flow,
            "chat_history_input_name": chat_history_input_name,
            "label": label,
            "chat_output_name": chat_output_name,
            "is_streaming": is_streaming,
        }

        with open(output_dir / "config.json", "w") as file:
            json.dump(config_content, file, indent=4)

        generate_hidden_imports, all_packages, meta_packages = self._generate_executable_dependency()
        hidden_imports.extend(generate_hidden_imports)
        copy_tree_respect_template_and_ignore_file(
            source=Path(__file__).parent.parent / "data" / "executable",
            target=output_dir,
            render_context={
                "hidden_imports": hidden_imports,
                "runtime_interpreter_path": runtime_interpreter_path,
                "all_packages": all_packages,
                "meta_packages": meta_packages,
            },
        )
        self._run_pyinstaller(output_dir)

    def _generate_executable_dependency(self):
        with open(Path(__file__).parent.parent / "data" / "executable" / "requirements.txt", "r") as f:
            all_packages = f.read().splitlines()

        if platform.system() != "Windows":
            all_packages = [pkg for pkg in all_packages if pkg.lower() != "pywin32"]

        hidden_imports = copy.deepcopy(all_packages)
        meta_packages = copy.deepcopy(all_packages)
        special_packages = ["streamlit-quill", "flask-cors", "flask-restx"]
        for i in range(len(hidden_imports)):
            # need special handling because it uses _ to import
            if hidden_imports[i] in special_packages:
                hidden_imports[i] = hidden_imports[i].replace("-", "_").lower()
            else:
                hidden_imports[i] = hidden_imports[i].replace("-", ".").lower()

        return hidden_imports, all_packages, meta_packages

    def _run_pyinstaller(self, output_dir):
        add_executable_script_to_env_path()
        with _change_working_dir(output_dir, mkdir=False):
            try:
                subprocess.run(["pyinstaller", "app.spec"], check=True)
                print("PyInstaller command executed successfully.")

                exe_dir = os.path.join(output_dir, "dist")
                for file_name in ["pf.bat", "pf", "start_pfs.vbs"]:
                    src_file = os.path.join(output_dir, file_name)
                    dst_file = os.path.join(exe_dir, file_name)
                    shutil.copy(src_file, dst_file)
                    st = os.stat(dst_file)
                    os.chmod(dst_file, st.st_mode | stat.S_IEXEC)
            except FileNotFoundError as e:
                raise UserErrorException(
                    message_format="The pyinstaller command was not found. Please ensure that the "
                    "executable directory of the current python environment has "
                    "been added to the PATH environment variable."
                ) from e

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

        flow = load_flow(flow)
        is_csharp_flow = flow.language == FlowLanguage.CSharp
        is_flex_flow = isinstance(flow, FlexFlow)
        is_prompty_flow = isinstance(flow, Prompty)

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
            update_flow_tools_json=False if is_csharp_flow or is_flex_flow or is_prompty_flow else True,
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
        from promptflow._sdk._orchestrator import remove_additional_includes

        # Eager flow may not contain a yaml file, skip resolving additional includes
        def is_yaml_file(file_path):
            _, file_extension = os.path.splitext(file_path)
            return file_extension.lower() in (".yaml", ".yml")

        if is_yaml_file(flow_dag_path) and _get_additional_includes(flow_dag_path):
            # Merge the flow folder and additional includes to temp folder.
            # TODO: support a flow_file_path with a name different from flow.dag.yaml
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

        flow_entity: Flow = load_flow(source=flow, raise_error=False)

        # TODO: put off this if we do path existence check in FlowSchema on fields other than additional_includes
        validation_result = flow_entity._validate()

        if not isinstance(flow_entity, FlexFlow):
            # only DAG flow has tools meta
            source_path_mapping = {}
            flow_tools, tools_errors = self._generate_tools_meta(
                flow=flow_entity.path,
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
        validation_result.resolve_location_for_diagnostics(flow_entity.path.as_posix())

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
        from promptflow.client import PFClient
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
        flow = load_flow(source=flow)
        if is_flex_flow(yaml_dict=flow._data):
            # No tools meta for eager flow
            return {"package": {}, "code": {}}, {}
        elif isinstance(flow, Prompty):
            return {
                "package": {},
                "code": {
                    flow.path.name: {
                        "type": "llm",
                        "inputs": {k: {"type": [v.get("type", "string")]} for k, v in flow._data["inputs"].items()},
                    }
                },
            }, {}

        with self._resolve_additional_includes(flow._flow_file_path) as new_flow_dag_path:
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

        additional_includes = _get_additional_includes(flow._flow_file_path)
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

    @monitor_operation(activity_name="pf.flows._generate_flow_meta", activity_type=ActivityType.INTERNALCALL)
    def _generate_flow_meta(
        self,
        flow: Union[str, PathLike],
        *,
        timeout: int = FLOW_META_JSON_GEN_TIMEOUT,
        dump: bool = False,
        load_in_subprocess: bool = True,
    ) -> dict:
        """Generate flow meta for a specific flow or a specific node in the flow.

        This is a private interface for vscode extension, so do not change the interface unless necessary.

        Usage:
        from promptflow.client import PFClient
        PFClient().flows._generate_flow_meta(flow="flow.dag.yaml")

        :param flow: path to the flow directory or flow dag to export
        :type flow: Union[str, PathLike]
        :param timeout: timeout for generating flow meta
        :type timeout: int
        :param dump: whether to dump the flow meta to .promptflow/flow.json
        :type dump: bool
        :param load_in_subprocess: whether to load flow in subprocess. will set to False for VSCode extension since
            it's already executes in a separate process.
        :type load_in_subprocess: bool
        :return: dict of flow meta
        :rtype: Tuple[dict, dict]
        """
        flow: Union[Flow, FlexFlow] = load_flow(source=flow)
        if not isinstance(flow, FlexFlow):
            # No flow meta for DAG flow
            return {}

        with self._resolve_additional_includes(flow.path) as new_flow_dag_path:
            from promptflow._proxy import ProxyFactory

            return (
                ProxyFactory()
                .get_executor_proxy_cls(flow.language)
                .generate_flow_json(
                    flow_file=new_flow_dag_path,
                    working_dir=new_flow_dag_path.parent,
                    dump=dump,
                    timeout=timeout,
                    load_in_subprocess=load_in_subprocess,
                )
            )

    @staticmethod
    def _resolve_requirements_txt(python_requirements, code):
        if python_requirements:
            requirements_filename = Path(python_requirements).name
            if (Path(code) / requirements_filename).exists():
                raise UserErrorException(
                    f"Specified requirements file {requirements_filename} already exists in code, please rename it."
                )
            return requirements_filename
        if (code / DEFAULT_REQUIREMENTS_FILE_NAME).is_file():
            # use %code%/requirements.txt if not specified and existed
            return DEFAULT_REQUIREMENTS_FILE_NAME
        return None

    @staticmethod
    def _infer_signature(entry: Union[Callable, FlexFlow, Flow, Prompty], include_primitive_output: bool = False):
        if isinstance(entry, Prompty):
            from promptflow.contracts.tool import ValueType
            from promptflow.core._model_configuration import PromptyModelConfiguration

            flow_meta = {
                "inputs": entry._core_prompty._get_input_signature(),
            }
            output_signature = entry._core_prompty._get_output_signature(include_primitive_output)
            if output_signature:
                flow_meta["outputs"] = output_signature
            init_dict = {}
            for field in fields(PromptyModelConfiguration):
                init_dict[field.name] = {"type": ValueType.from_type(field.type).value}
                if field.default != MISSING:
                    init_dict[field.name]["default"] = field.default
            flow_meta["init"] = init_dict
            format_signature_type(flow_meta)
        elif isinstance(entry, FlexFlow):
            # non-python flow depends on dumped flow meta to infer signature
            ProxyFactory().create_inspector_proxy(language=entry.language).prepare_metadata(
                flow_file=entry.path,
                working_dir=entry.code,
            )
            flow_meta, _, _ = infer_signature_for_flex_flow(
                entry=entry.entry,
                code=entry.code.as_posix(),
                language=entry.language,
                include_primitive_output=include_primitive_output,
            )
        elif inspect.isclass(entry) or inspect.isfunction(entry):
            flow_meta, _, _ = infer_signature_for_flex_flow(
                entry=entry, include_primitive_output=include_primitive_output, language=FlowLanguage.Python
            )
        else:
            # TODO support to get infer signature of dag flow
            raise UserErrorException(f"Invalid entry {type(entry).__name__}, only support callable object or prompty.")
        return flow_meta

    @monitor_operation(activity_name="pf.flows.infer_signature", activity_type=ActivityType.PUBLICAPI)
    def infer_signature(self, entry: Union[Callable, FlexFlow, Flow, Prompty], **kwargs) -> dict:
        """Extract signature for a callable class or a function or a flow. Signature indicates the ports of a flex flow
        using the callable as entry.

        For flex flow:
            If entry is a callable function, the signature includes inputs and outputs.
            If entry is a callable class, the signature includes inputs, outputs, and init.

        For prompty flow:
            The signature includes inputs, outputs, and init. Init refers to PromptyModelConfiguration.

        For dag flow:
            The signature includes inputs and outputs.

        Type of each port is inferred from the type hints of the callable and follows type system of json schema.
        Given flow accepts json input in batch run and serve, we support only a part of types for those ports.
        Complicated types must be decorated with dataclasses.dataclass.
        Errors will be raised if annotated types are not supported.

        :param entry: entry of the flow, should be a method name relative to code
        :type entry: Callable
        :return: signature of the flow
        :rtype: dict
        """
        # TODO: should we support string entry? If so, we should also add a parameter to specify the working directory
        include_primitive_output = kwargs.get("include_primitive_output", False)
        flow_meta = self._infer_signature(entry=entry, include_primitive_output=include_primitive_output)
        return flow_meta

    def _save(
        self,
        entry: Union[str, Callable],
        code: Union[str, PathLike, None] = None,
        path: Union[str, PathLike, None] = None,
        *,
        python_requirements_txt: str = None,
        image: str = None,
        signature: dict = None,
        sample: dict = None,
        **kwargs,
    ) -> NoReturn:
        # hide the language field before csharp support go public
        language: str = kwargs.get(LANGUAGE_KEY, FlowLanguage.Python)

        entry_meta, code, snapshot_list = infer_signature_for_flex_flow(
            entry, code=code, keep_entry=True, validate=False, language=language
        )

        data = merge_flow_signature(entry_meta, signature)
        data["entry"] = entry_meta["entry"]

        # python_requirements_txt
        # avoid editing the original python_requirements as it will be used in copy stage
        _python_requirements = self._resolve_requirements_txt(python_requirements_txt, code)
        if _python_requirements:
            pydash.set_(data, "environment.python_requirements_txt", _python_requirements)

        if image:
            pydash.set_(data, "environment.image", image)

        if LANGUAGE_KEY in kwargs:
            data[LANGUAGE_KEY] = language

        # schema validation, here target_flow_file doesn't exist actually
        # TODO: allow flex flow without path
        FlexFlow(path=code / FLOW_FLEX_YAML, code=code, data=data, entry=data["entry"])._validate(raise_error=True)

        if path:
            # copy code to target directory if path is specified
            target_flow_directory = Path(path)
            if target_flow_directory.exists() and len(os.listdir(target_flow_directory.as_posix())) != 0:
                raise UserErrorException(f"Target path {target_flow_directory.as_posix()} exists and is not empty.")
            target_flow_directory.parent.mkdir(parents=True, exist_ok=True)

            # TODO: handle ignore
            if snapshot_list is not None:
                for snapshot in snapshot_list:
                    shutil.copy(code / snapshot, target_flow_directory / snapshot)
            else:
                shutil.copytree(
                    code, target_flow_directory, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__")
                )
        else:
            # or we update the flow definition yaml file in code only
            target_flow_directory = code
            target_flow_directory.parent.mkdir(parents=True, exist_ok=True)

        target_flow_file = target_flow_directory / FLOW_FLEX_YAML

        if python_requirements_txt:
            shutil.copy(python_requirements_txt, target_flow_directory / Path(python_requirements_txt).name)

        if sample:
            inputs = data.get("inputs", {})
            sample_inputs = sample.get("inputs", {})
            if not isinstance(sample_inputs, dict):
                raise UserErrorException("Sample must be a dict.")
            if not set(sample_inputs.keys()) == set(inputs.keys()):
                raise UserErrorException(
                    message_format="Sample keys {actual} do not match the inputs {expected}.",
                    actual=", ".join(sample_inputs.keys()),
                    expected=", ".join(inputs.keys()),
                )
            with open(target_flow_directory / SERVE_SAMPLE_JSON_PATH, "w", encoding=DEFAULT_ENCODING) as f:
                json.dump(sample, f, indent=4)
            data["sample"] = f"${{file:{SERVE_SAMPLE_JSON_PATH}}}"
        with open(target_flow_file, "w", encoding=DEFAULT_ENCODING):
            dump_yaml(data, target_flow_file)

    @monitor_operation(activity_name="pf.flows.save", activity_type=ActivityType.PUBLICAPI)
    def save(
        self,
        entry: Union[str, Callable],
        code: Union[str, PathLike, None] = None,
        path: Union[str, PathLike, None] = None,
        *,
        python_requirements_txt: str = None,
        image: str = None,
        signature: dict = None,
        sample: Union[str, PathLike, dict] = None,
        **kwargs,
    ) -> NoReturn:
        """
        Save a callable class or a function as a flex flow.

        :param entry: entry of the flow. If entry is a string, code will be required and entry should be a
            method name relative to code, like "module.method". If entry is a callable class or a function,
            code must be left None.
        :type entry: Union[str, Callable]
        :param code: path to the code directory. Will be copied to the target directory. If entry is a callable,
            code must be left None and the parent directory of the entry source will be used as code.
        :type code: Union[str, PathLike]
        :param path: target directory to create the flow. If specified, it must be an empty or non-existent directory;
            if not specified, will update the flow definition yaml file in code.
        :type path: Union[str, PathLike]
        :param python_requirements_txt: path to the python requirements file. If not specified, will use
              `requirements.txt` if existed in code directory.
        :type python_requirements_txt: str
        :param image: image to run the flow. Will use default image if not specified.
        :type image: str
        :param signature: signature of the flow, indicates the input and output ports of the flow
        :type signature: dict
        :param sample: sample input data for the flow. Will be used for swagger generation in `flow serve`.
        :type sample: dict
        :return: no return
        :rtype: None
        """
        # this transformation is put here to limit the scope of _save. Inner call should not involve a file sample.
        if isinstance(sample, (str, Path, PathLike)):
            with open(sample, "r", encoding=DEFAULT_ENCODING) as f:
                sample = json.load(f)

        return self._save(
            path=path,
            entry=entry,
            code=code,
            python_requirements_txt=python_requirements_txt,
            image=image,
            signature=signature,
            sample=sample,
            **kwargs,
        )

    def _get_telemetry_values(self, *args, **kwargs):
        activity_name = kwargs.get("activity_name", None)
        telemetry_values = super()._get_telemetry_values(*args, **kwargs)
        try:
            if activity_name == "pf.flows.test":
                flow = kwargs.get("flow", None) or args[0]
                telemetry_values["flow_type"] = get_flow_type(flow)
        except Exception as e:
            logger.error(f"Failed to get telemetry values: {str(e)}")

        return telemetry_values
