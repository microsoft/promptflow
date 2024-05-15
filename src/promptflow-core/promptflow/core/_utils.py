# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
import os
import re
from configparser import ConfigParser
from os import PathLike
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

from jinja2 import Template

from promptflow._constants import AZURE_WORKSPACE_REGEX_FORMAT
from promptflow._utils.flow_utils import is_flex_flow, is_prompty_flow, resolve_flow_path
from promptflow._utils.logger_utils import LoggerFactory
from promptflow._utils.utils import _match_reference
from promptflow._utils.yaml_utils import load_yaml
from promptflow.core._errors import InvalidSampleError, MalformedConnectionProviderConfig, MissingRequiredPackage
from promptflow.exceptions import UserErrorException

logger = LoggerFactory.get_logger(name=__name__)


def render_jinja_template_content(template_content, *, trim_blocks=True, keep_trailing_newline=True, **kwargs):
    template = Template(template_content, trim_blocks=trim_blocks, keep_trailing_newline=keep_trailing_newline)
    return template.render(**kwargs)


def init_executable(*, flow_data: dict = None, flow_path: Path = None, working_dir: Path = None):
    if flow_data and flow_path:
        raise ValueError("flow_dag and flow_path cannot be both provided.")
    if not flow_data and not flow_path:
        raise ValueError("flow_dag or flow_path must be provided.")
    if flow_data and not working_dir:
        raise ValueError("working_dir must be provided when flow_dag is provided.")

    if flow_path:
        if is_prompty_flow(file_path=flow_path):
            from promptflow.contracts.flow import PromptyFlow as ExecutablePromptyFlow
            from promptflow.core._flow import Prompty

            configs, _ = Prompty._parse_prompty(flow_path)
            return ExecutablePromptyFlow._from_dict(flow_data=configs, working_dir=working_dir or flow_path.parent)

        flow_dir, flow_filename = resolve_flow_path(flow_path)
        flow_data = load_yaml(flow_dir / flow_filename)

        # priority: code in yaml > working_dir > flow_dir
        if "code" not in flow_data:
            working_dir = working_dir or flow_dir
        elif os.path.isabs(flow_data["code"]):
            working_dir = Path(flow_data["code"])
        else:
            working_dir = flow_dir / Path(flow_data["code"])

    from promptflow.contracts.flow import FlexFlow as ExecutableEagerFlow
    from promptflow.contracts.flow import Flow as ExecutableFlow

    if is_flex_flow(yaml_dict=flow_data):
        return ExecutableEagerFlow._from_dict(flow_data=flow_data, working_dir=working_dir)

    # for DAG flow, use data to init executable to improve performance
    return ExecutableFlow._from_dict(flow_data=flow_data, working_dir=working_dir)


# !!! Attention!!!: Please make sure you have contact with PRS team before changing the interface.
# They are using FlowExecutor.update_environment_variables_with_connections(connections)
def update_environment_variables_with_connections(built_connections):
    """The function will result env var value ${my_connection.key} to the real connection keys."""
    return update_dict_value_with_connections(built_connections, os.environ)


def override_connection_config_with_environment_variable(connections: Dict[str, dict]):
    """
    The function will use relevant environment variable to override connection configurations. For instance, if there
    is a custom connection named 'custom_connection' with a configuration key called 'chat_deployment_name,' the
    function will attempt to retrieve 'chat_deployment_name' from the environment variable
    'CUSTOM_CONNECTION_CHAT_DEPLOYMENT_NAME' by default. If the environment variable is not set, it will use the
    original value as a fallback.
    """
    for connection_name, connection in connections.items():
        values = connection.get("value", {})
        for key, val in values.items():
            connection_name = connection_name.replace(" ", "_")
            env_name = f"{connection_name}_{key}".upper()
            if env_name not in os.environ:
                continue
            values[key] = os.environ[env_name]
            logger.info(f"Connection {connection_name}'s {key} is overridden with environment variable {env_name}")
    return connections


def resolve_connections_environment_variable_reference(connections: Dict[str, dict]):
    """The function will resolve connection secrets env var reference like api_key: ${env:KEY}"""
    for connection in connections.values():
        values = connection.get("value", {})
        for key, val in values.items():
            if not _match_env_reference(val):
                continue
            env_name = _match_env_reference(val)
            if env_name not in os.environ:
                raise UserErrorException(f"Environment variable {env_name} is not found.")
            values[key] = os.environ[env_name]
    return connections


def _match_env_reference(val: str):
    try:
        val = val.strip()
        m = re.match(r"^\$\{env:(.+)}$", val)
        if not m:
            return None
        name = m.groups()[0]
        return name
    except Exception:
        # for exceptions when val is not a string, return
        return None


def get_used_connection_names_from_environment_variables():
    """The function will get all potential related connection names from current environment variables.
    for example, if part of env var is
    {
      "ENV_VAR_1": "${my_connection.key}",
      "ENV_VAR_2": "${my_connection.key2}",
      "ENV_VAR_3": "${my_connection2.key}",
    }
    The function will return {"my_connection", "my_connection2"}.
    """
    return get_used_connection_names_from_dict(os.environ)


def update_dict_value_with_connections(built_connections, connection_dict: dict):
    for key, val in connection_dict.items():
        connection_name, connection_key = _match_reference(val)
        if connection_name is None:
            continue
        if connection_name not in built_connections:
            continue
        if connection_key not in built_connections[connection_name]["value"]:
            continue
        connection_dict[key] = built_connections[connection_name]["value"][connection_key]


def get_used_connection_names_from_dict(connection_dict: dict):
    connection_names = set()
    for key, val in connection_dict.items():
        connection_name, _ = _match_reference(val)
        if connection_name:
            connection_names.add(connection_name)

    return connection_names


def extract_workspace(provider_config) -> Tuple[str, str, str]:
    match = re.match(AZURE_WORKSPACE_REGEX_FORMAT, provider_config)
    if not match or len(match.groups()) != 5:
        raise MalformedConnectionProviderConfig(provider_config=provider_config)
    subscription_id = match.group(1)
    resource_group = match.group(3)
    workspace_name = match.group(5)
    return subscription_id, resource_group, workspace_name


def get_workspace_from_resource_id(resource_id: str, credential, pkg_name: Optional[str] = None):
    # check azure extension first
    try:
        from azure.ai.ml import MLClient
    except ImportError as e:
        if pkg_name is not None:
            error_msg = f"Please install '{pkg_name}' to use Azure related features."
        else:
            error_msg = (
                "Please install Azure extension (e.g. `pip install promptflow-azure`) to use Azure related features."
            )
        raise MissingRequiredPackage(message=error_msg) from e
    # extract workspace triad and get from Azure
    subscription_id, resource_group_name, workspace_name = extract_workspace(resource_id)
    ml_client = MLClient(
        credential=credential,
        subscription_id=subscription_id,
        resource_group_name=resource_group_name,
        workspace_name=workspace_name,
    )
    return ml_client.workspaces.get(name=workspace_name)


def load_inputs_from_sample(sample: Union[dict, str, PathLike]):
    if not sample:
        return {}
    elif isinstance(sample, dict):
        return sample
    elif isinstance(sample, (str, Path)) and str(sample).endswith(".json"):
        if str(sample).startswith("file:"):
            sample = sample[len("file:") :]
        if not Path(sample).exists():
            raise InvalidSampleError(f"Cannot find sample file {sample}.")
        with open(sample, "r") as f:
            return json.load(f)
    else:
        raise InvalidSampleError("Only dict and json file are supported as sample in prompty.")


def get_workspace_triad_from_local() -> tuple:
    subscription_id = None
    resource_group_name = None
    workspace_name = None
    azure_config_path = Path.home() / ".azure"
    config_parser = ConfigParser()
    # subscription id
    try:
        config_parser.read_file(open(azure_config_path / "clouds.config"))
        subscription_id = config_parser["AzureCloud"]["subscription"]
    except Exception:  # pylint: disable=broad-except
        pass
    # resource group name & workspace name
    try:
        config_parser.read_file(open(azure_config_path / "config"))
        resource_group_name = config_parser["defaults"]["group"]
        workspace_name = config_parser["defaults"]["workspace"]
    except Exception:  # pylint: disable=broad-except
        pass
    return subscription_id, resource_group_name, workspace_name
