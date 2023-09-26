# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging
import os.path
import uuid
from itertools import product
from os import PathLike
from pathlib import Path
from typing import Optional, Union

import pydash

from promptflow._sdk._constants import LOGGER_NAME, ConnectionProvider
from promptflow._sdk._logger_factory import LoggerFactory
from promptflow._sdk._utils import call_from_extension, dump_yaml, load_yaml
from promptflow.exceptions import ErrorTarget, ValidationException

logger = LoggerFactory.get_logger(name=LOGGER_NAME, verbosity=logging.WARNING)


class ConfigFileNotFound(ValidationException):
    pass


class Configuration(object):

    CONFIG_PATH = Path.home() / ".promptflow" / "pf.yaml"
    COLLECT_TELEMETRY = "cli.telemetry_enabled"
    EXTENSION_COLLECT_TELEMETRY = "extension.telemetry_enabled"
    INSTALLATION_ID = "cli.installation_id"
    CONNECTION_PROVIDER = "connection.provider"
    _instance = None

    def __init__(self):
        if not os.path.exists(self.CONFIG_PATH.parent):
            os.makedirs(self.CONFIG_PATH.parent, exist_ok=True)
        if not os.path.exists(self.CONFIG_PATH):
            with open(self.CONFIG_PATH, "w") as f:
                f.write(dump_yaml({}))
        self._config = load_yaml(self.CONFIG_PATH)
        if not self._config:
            self._config = {}

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
        pydash.set_(self._config, key, value)
        with open(self.CONFIG_PATH, "w") as f:
            f.write(dump_yaml(self._config))

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
        return RESOURCE_ID_FORMAT.format(subscription_id, resource_group, AZUREML_RESOURCE_PROVIDER, workspace_name)

    def get_connection_provider(self) -> Optional[str]:
        """Get the current connection provider. Default to local if not configured."""
        provider = self.get_config(key=self.CONNECTION_PROVIDER)
        if provider is None:
            return ConnectionProvider.LOCAL
        if provider is ConnectionProvider.AZURE:
            # Note: The below function has azure-ai-ml dependency.
            return "azureml:" + self._get_workspace_from_config()
        # If provider not None and not Azure, return it directly.
        # It can be the full path of a workspace.
        return provider

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
        user_id = self.get_config(key=self.INSTALLATION_ID)
        if user_id:
            return user_id
        else:
            user_id = str(uuid.uuid4())
            self.set_config(key=self.INSTALLATION_ID, value=user_id)
            return user_id

    def _to_dict(self):
        return self._config
