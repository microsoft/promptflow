# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path

from promptflow._constants import DEFAULT_ENCODING
from promptflow._sdk._configuration import Configuration
from promptflow._sdk._serving.blueprint.monitor_blueprint import construct_monitor_blueprint
from promptflow._sdk._serving.blueprint.static_web_blueprint import construct_staticweb_blueprint
from promptflow._sdk._serving.monitor.flow_monitor import FlowMonitor
from promptflow._utils.yaml_utils import load_yaml
from promptflow._version import VERSION
from promptflow.contracts.flow import Flow

USER_AGENT = f"promptflow-local-serving/{VERSION}"
DEFAULT_STATIC_PATH = Path(__file__).parent.parent / "static"


class AppExtension(ABC):
    def __init__(self, logger, **kwargs):
        self.logger = logger

    @abstractmethod
    def get_flow_project_path(self) -> str:
        """Get flow project path."""
        pass

    @abstractmethod
    def get_flow_name(self) -> str:
        """Get flow name."""
        pass

    @abstractmethod
    def get_connection_provider(self) -> str:
        """Get connection provider."""
        pass

    @abstractmethod
    def get_blueprints(self):
        """Get blueprints for current extension."""
        pass

    def get_override_connections(self, flow: Flow) -> (dict, dict):
        """
        Get override connections for current extension.

        :param flow: The flow to execute.
        :type flow: ~promptflow._sdk.entities._flow.Flow
        :return: The override connections, first dict is for connection data override, second dict is for connection name override.  # noqa: E501
        :rtype: (dict, dict)
        """
        return {}, {}

    def raise_ex_on_invoker_initialization_failure(self, ex: Exception):
        """
        whether to raise exception when initializing flow invoker failed.

        :param ex: The exception when initializing flow invoker.
        :type ex: Exception
        :return: Whether to raise exception when initializing flow invoker failed.
        """
        return True

    def get_user_agent(self) -> str:
        """Get user agent used for current extension."""
        return USER_AGENT

    def get_credential(self):
        """Get credential for current extension."""
        return None

    def get_metrics_common_dimensions(self):
        """Get common dimensions for metrics if exist."""
        return self._get_common_dimensions_from_env()

    def get_flow_monitor(self) -> FlowMonitor:
        """Get flow monitor for current extension."""
        # default no data collector, no app insights metric exporter
        return FlowMonitor(self.logger, self.get_flow_name(), None, metrics_recorder=None)

    def _get_mlflow_project_path(self, project_path: str):
        # check whether it's mlflow model
        mlflow_metadata_file = os.path.join(project_path, "MLmodel")
        if os.path.exists(mlflow_metadata_file):
            with open(mlflow_metadata_file, "r", encoding=DEFAULT_ENCODING) as fin:
                mlflow_metadata = load_yaml(fin)
            flow_entry = mlflow_metadata.get("flavors", {}).get("promptflow", {}).get("entry")
            if mlflow_metadata:
                dag_path = os.path.join(project_path, flow_entry)
                return str(Path(dag_path).parent.absolute())
        return project_path

    def _get_common_dimensions_from_env(self):
        common_dimensions_str = os.getenv("PF_SERVING_METRICS_COMMON_DIMENSIONS", None)
        if common_dimensions_str:
            try:
                common_dimensions = json.loads(common_dimensions_str)
                return common_dimensions
            except Exception as ex:
                self.logger.warn(f"Failed to parse common dimensions with value={common_dimensions_str}: {ex}")
        return {}

    def _get_default_blueprints(self, static_folder=None):
        static_web_blueprint = construct_staticweb_blueprint(static_folder)
        monitor_print = construct_monitor_blueprint(self.get_flow_monitor())
        return [static_web_blueprint, monitor_print]


class DefaultAppExtension(AppExtension):
    """default app extension for local serve."""

    def __init__(self, logger, **kwargs):
        self.logger = logger
        static_folder = kwargs.get("static_folder", None)
        self.static_folder = static_folder if static_folder else DEFAULT_STATIC_PATH
        logger.info(f"Static_folder: {self.static_folder}")
        app_config = kwargs.get("config", None) or {}
        pf_config = Configuration(overrides=app_config)
        logger.info(f"Promptflow config: {pf_config}")
        self.connection_provider = pf_config.get_connection_provider()

    def get_flow_project_path(self) -> str:
        return os.getenv("PROMPTFLOW_PROJECT_PATH", ".")

    def get_flow_name(self) -> str:
        project_path = self.get_flow_project_path()
        return Path(project_path).stem

    def get_connection_provider(self) -> str:
        return self.connection_provider

    def get_blueprints(self):
        return self._get_default_blueprints(self.static_folder)
