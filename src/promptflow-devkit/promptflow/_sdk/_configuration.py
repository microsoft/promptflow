# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging
import os.path
from contextlib import contextmanager
from itertools import product
from os import PathLike
from pathlib import Path
from typing import Optional, Union

import pydash

from promptflow._constants import ConnectionProviderConfig
from promptflow._sdk._constants import (
    DEFAULT_ENCODING,
    FLOW_DIRECTORY_MACRO_IN_CONFIG,
    HOME_PROMPT_FLOW_DIR,
    PF_SERVICE_HOST,
    REMOTE_URI_PREFIX,
    SERVICE_CONFIG_FILE,
)
from promptflow._sdk._utilities.general_utils import call_from_extension, gen_uuid_by_compute_info, read_write_by_user
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow._utils.yaml_utils import dump_yaml, load_yaml
from promptflow.exceptions import ErrorTarget, UserErrorException, ValidationException

logger = get_cli_sdk_logger()


class ConfigFileNotFound(ValidationException):
    pass


class InvalidConfigFile(ValidationException):
    pass


class InvalidConfigValue(ValidationException):
    pass


class Configuration(object):
    GLOBAL_CONFIG_PATH = Path(HOME_PROMPT_FLOW_DIR) / SERVICE_CONFIG_FILE
    CONFIG_PATH = GLOBAL_CONFIG_PATH
    COLLECT_TELEMETRY = "telemetry.enabled"
    EXTENSION_COLLECT_TELEMETRY = "extension.telemetry_enabled"
    INSTALLATION_ID = "cli.installation_id"
    CONNECTION_PROVIDER = "connection.provider"
    RUN_OUTPUT_PATH = "run.output_path"
    USER_AGENT = "user_agent"
    ENABLE_INTERNAL_FEATURES = "enable_internal_features"
    TRACE_DESTINATION = "trace.destination"
    PFS_HOST = "service.host"
    _instance = None

    def __init__(self, overrides=None):
        self._config = self._get_cwd_config()
        # Allow config override by kwargs
        overrides = overrides or {}
        for key, value in overrides.items():
            self._validate(key, value)
            pydash.set_(self._config, key, value)

    def _get_cwd_config(self):
        cwd_config_path = Path.cwd().absolute().resolve()
        file_name = self.CONFIG_PATH.name
        while not (cwd_config_path / file_name).is_file() and cwd_config_path.parent != cwd_config_path:
            cwd_config_path = cwd_config_path.parent

        if (cwd_config_path / file_name).is_file():
            cwd_config = load_yaml(cwd_config_path / file_name)
        else:
            cwd_config = {}

        if self.CONFIG_PATH.is_file():
            global_config = load_yaml(self.CONFIG_PATH)
            cwd_config.update(global_config)

        return cwd_config

    @property
    def config(self):
        return self._config

    @classmethod
    def get_instance(cls):
        """Use this to get instance to avoid multiple copies of same global config."""
        if cls._instance is None:
            cls._instance = Configuration()
        return cls._instance

    def set_config(self, key, value):
        """Store config in file to avoid concurrent write."""
        self._validate(key, value)
        if self.CONFIG_PATH.is_file():
            config = load_yaml(self.CONFIG_PATH)
        else:
            os.makedirs(self.CONFIG_PATH.parent, exist_ok=True)
            self.CONFIG_PATH.touch(mode=read_write_by_user(), exist_ok=True)
            config = {}

        pydash.set_(config, key, value)
        with open(self.CONFIG_PATH, "w", encoding=DEFAULT_ENCODING) as f:
            dump_yaml(config, f)

        # If this config is added to the global config file or the parent directory config file of cwd,
        # then (key, value) needs to be added to cwd config content.
        if self.CONFIG_PATH == self.GLOBAL_CONFIG_PATH or Path().cwd().absolute().resolve().as_posix().startswith(
            self.CONFIG_PATH.parent.absolute().resolve().as_posix()
        ):
            pydash.set_(self._config, key, value)

    def get_config(self, key):
        try:
            return pydash.get(self._config, key, None)
        except Exception:  # pylint: disable=broad-except
            return None

    def get_all(self):
        return self._config

    @classmethod
    def _get_workspace_from_config(
        cls,
        *,
        path: Union[PathLike, str] = None,
    ) -> str:
        """Return a workspace arm id from an existing Azure Machine Learning Workspace.
        Reads workspace configuration from a file. Throws an exception if the config file can't be found.

        :param path: The path to the config file or starting directory to search.
            The parameter defaults to starting the search in the current directory.
        :type path: str
        :return: The workspace arm id for an existing Azure ML Workspace.
        :rtype: ~str
        """
        from azure.ai.ml import MLClient
        from azure.ai.ml._file_utils.file_utils import traverse_up_path_and_find_file
        from azure.ai.ml.constants._common import AZUREML_RESOURCE_PROVIDER, RESOURCE_ID_FORMAT

        path = Path(".") if path is None else Path(path)
        if path.is_file():
            found_path = path
        else:
            # Based on priority
            # Look in config dirs like .azureml or plain directory
            # with None
            directories_to_look = [".azureml", None]
            files_to_look = ["config.json"]

            found_path = None
            for curr_dir, curr_file in product(directories_to_look, files_to_look):
                logging.debug(
                    "No config file directly found, starting search from %s "
                    "directory, for %s file name to be present in "
                    "%s subdirectory",
                    path,
                    curr_file,
                    curr_dir,
                )

                found_path = traverse_up_path_and_find_file(
                    path=path,
                    file_name=curr_file,
                    directory_name=curr_dir,
                    num_levels=20,
                )
                if found_path:
                    break

            if not found_path:
                msg = (
                    "We could not find config.json in: {} or in its parent directories. "
                    "Please provide the full path to the config file or ensure that "
                    "config.json exists in the parent directories."
                )
                raise ConfigFileNotFound(
                    message=msg.format(path),
                    no_personal_data_message=msg.format("[path]"),
                    target=ErrorTarget.CONTROL_PLANE_SDK,
                )

        subscription_id, resource_group, workspace_name = MLClient._get_workspace_info(found_path)
        if not (subscription_id and resource_group and workspace_name):
            raise InvalidConfigFile(
                "The subscription_id, resource_group and workspace_name can not be empty. Got: "
                f"subscription_id: {subscription_id}, resource_group: {resource_group}, "
                f"workspace_name: {workspace_name} from file {found_path}."
            )
        return RESOURCE_ID_FORMAT.format(subscription_id, resource_group, AZUREML_RESOURCE_PROVIDER, workspace_name)

    def get_connection_provider(self, path=None) -> Optional[str]:
        """Get the current connection provider. Default to local if not configured."""
        provider = self.get_config(key=self.CONNECTION_PROVIDER)
        return self.resolve_connection_provider(provider, path=path)

    @classmethod
    def resolve_connection_provider(cls, provider, path=None) -> Optional[str]:
        if provider is None:
            return ConnectionProviderConfig.LOCAL
        if provider == ConnectionProviderConfig.AZUREML:
            # Note: The below function has azure-ai-ml dependency.
            return "azureml:" + cls._get_workspace_from_config(path=path)
        # If provider not None and not Azure, return it directly.
        # It can be the full path of a workspace.
        return provider

    def get_trace_destination(self, path: Optional[Path] = None) -> Optional[str]:
        from promptflow._sdk._tracing import TraceDestinationConfig

        value = self.get_config(key=self.TRACE_DESTINATION)
        logger.info("pf.config.trace.destination: %s", value)
        if TraceDestinationConfig.need_to_resolve(value):
            logger.debug("will resolve trace destination from config.json...")
            return self._resolve_trace_destination(path=path)
        else:
            logger.debug("trace destination does not need to be resolved, directly return...")
            return value

    def _is_cloud_trace_destination(self, path: Optional[Path] = None) -> bool:
        trace_destination = self.get_trace_destination(path=path)
        is_cloud = trace_destination and trace_destination.startswith(REMOTE_URI_PREFIX)
        if is_cloud:
            try:
                from promptflow.azure import PFClient  # noqa: F401
            except ImportError as e:
                error_message = (
                    f'Trace provider is set to cloud. "promptflow[azure]" is required for local to cloud tracing '
                    f'experience, please install it by running "pip install promptflow[azure]". '
                    f"Original error: {str(e)}"
                )
                raise UserErrorException(message=error_message) from e
        return is_cloud

    def _resolve_trace_destination(self, path: Optional[Path] = None) -> str:
        return "azureml:/" + self._get_workspace_from_config(path=path)

    def get_telemetry_consent(self) -> Optional[bool]:
        """Get the current telemetry consent value. Return None if not configured."""
        if call_from_extension():
            return self.get_config(key=self.EXTENSION_COLLECT_TELEMETRY)
        return self.get_config(key=self.COLLECT_TELEMETRY)

    def set_telemetry_consent(self, value):
        """Set the telemetry consent value and store in local."""
        self.set_config(key=self.COLLECT_TELEMETRY, value=value)

    def get_or_set_installation_id(self):
        """Get user id if exists, otherwise set installation id and return it."""
        installation_id = self.get_config(key=self.INSTALLATION_ID)
        if installation_id:
            return installation_id

        installation_id = gen_uuid_by_compute_info()
        self.set_config(key=self.INSTALLATION_ID, value=installation_id)
        return installation_id

    def get_run_output_path(self) -> Optional[str]:
        """Get the run output path in local."""
        return self.get_config(key=self.RUN_OUTPUT_PATH)

    def _to_dict(self):
        return self._config

    @staticmethod
    def _validate(key: str, value: str) -> None:
        if key == Configuration.RUN_OUTPUT_PATH:
            if value.rstrip("/").endswith(FLOW_DIRECTORY_MACRO_IN_CONFIG):
                raise InvalidConfigValue(
                    "Cannot specify flow directory as run output path; "
                    "if you want to specify run output path under flow directory, "
                    "please use its child folder, e.g. '${flow_directory}/.runs'."
                )
        elif key == Configuration.TRACE_DESTINATION:
            from promptflow._sdk._tracing import TraceDestinationConfig

            TraceDestinationConfig.validate(value)
        return

    def get_user_agent(self) -> Optional[str]:
        """Get customer set user agent. If set, will add prefix `PFCustomer_`"""
        user_agent = self.get_config(key=self.USER_AGENT)
        if user_agent:
            return f"PFCustomer_{user_agent}"
        return user_agent

    def is_internal_features_enabled(self) -> Optional[bool]:
        """Get enable_preview_features"""
        result = self.get_config(key=self.ENABLE_INTERNAL_FEATURES)
        if isinstance(result, str):
            return result.lower() == "true"
        return result is True

    @classmethod
    @contextmanager
    def set_temp_config_path(cls, temp_path: Union[str, Path]):
        temp_path = Path(temp_path).resolve().absolute()
        if temp_path.is_file():
            raise InvalidConfigFile(
                "The configuration file folder is not set correctly. " "It cannot be a file, it can only be a folder"
            )
        original_path = cls.CONFIG_PATH
        file_name = cls.CONFIG_PATH.name
        cls.CONFIG_PATH = temp_path / file_name
        yield
        cls.CONFIG_PATH = original_path

    def get_pfs_host(self) -> Optional[str]:
        """Get the prompt flow service host."""
        return self.get_config(key=self.PFS_HOST) or PF_SERVICE_HOST
